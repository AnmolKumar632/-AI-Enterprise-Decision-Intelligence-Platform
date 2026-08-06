import re
import pandas as pd
import numpy as np
from utilities.custom_logger import get_logger

logger = get_logger('nlp_interpreter')

class NLQueryInterpreter:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        
    def _find_column(self, keywords, default=None):
        """Find a column in the dataframe matching keywords."""
        for col in self.df.columns:
            for kw in keywords:
                if kw.lower() in col.lower():
                    return col
        return default

    def interpret(self, query: str) -> dict:
        """Interpret a natural language question and return analytics + explanations."""
        query_lower = query.lower().strip()
        
        # Identify common business columns with expanded synonyms
        sales_col = self._find_column(['sales', 'revenue', 'turnover', 'purchase amount', 'amount', 'price'], default=None)
        profit_col = self._find_column(['profit', 'margin', 'gain'], default=None)
        region_col = self._find_column(['region', 'state', 'country', 'city', 'location', 'loc', 'geography'], default=None)
        product_col = self._find_column(['product', 'item', 'sku', 'category', 'type', 'name'], default=None)
        date_col = self._find_column(['date', 'month', 'year', 'timestamp'], default=None)
        
        # 1. QUESTION: Which region/location has maximum profit/sales?
        is_geo_query = any(k in query_lower for k in ['region', 'location', 'where', 'state', 'city'])
        is_max_query = any(k in query_lower for k in ['max', 'highest', 'best', 'most', 'top', 'maximum'])
        
        if is_geo_query and is_max_query:
            target_col = profit_col or sales_col
            if not region_col:
                return {
                    "text": "I couldn't automatically resolve a region, state, or geography column in this dataset. Please verify if your dataset has a location-related field.",
                    "chart": None
                }
            if not target_col:
                return {
                    "text": "I couldn't identify a numeric sales, revenue, or profit column in this dataset to aggregate performance metrics.",
                    "chart": None
                }
                
            grouped = self.df.groupby(region_col)[target_col].sum().reset_index()
            grouped = grouped.sort_values(by=target_col, ascending=False)
            
            top_region = grouped.iloc[0][region_col]
            top_val = grouped.iloc[0][target_col]
            total_val = grouped[target_col].sum()
            pct = (top_val / total_val * 100) if total_val > 0 else 0
            
            text = (
                f"Based on the aggregate analysis of geographical data, the highest-performing location is **'{top_region}'**, "
                f"generating a total {target_col} of **${round(top_val, 2)}**. This accounts for **{round(pct, 1)}%** of the "
                f"total **${round(total_val, 2)}** aggregated across all regions in your active dataset."
            )
            
            chart = {
                "type": "bar",
                "labels": [str(x) for x in grouped[region_col].tolist()],
                "values": [float(x) for x in grouped[target_col].tolist()],
                "label": f"Total {target_col.capitalize()} by Region"
            }
            return {"text": text, "chart": chart}
            
        # 2. QUESTION: Why did sales decrease?
        is_decline_query = any(k in query_lower for k in ['decrease', 'drop', 'decline', 'why did', 'down', 'loss', 'fall'])
        if is_decline_query:
            target_col = sales_col or profit_col
            if not target_col:
                return {"text": "I couldn't find a numeric metric column (like sales or revenue) to calculate trend lines.", "chart": None}
            if not date_col:
                return {"text": "A date-time field is required to determine historical month-over-month declines.", "chart": None}
                
            # Aggregate monthly
            temp_df = self.df.copy()
            temp_df[date_col] = pd.to_datetime(temp_df[date_col])
            monthly = temp_df.set_index(date_col).resample('ME')[target_col].sum().reset_index()
            
            if len(monthly) < 2:
                return {"text": "The active dataset contains less than two months of historical intervals, which is insufficient to compute growth/decline rate drops.", "chart": None}
                
            monthly['pct_change'] = monthly[target_col].pct_change() * 100
            drops = monthly[monthly['pct_change'] < 0]
            
            if drops.empty:
                return {"text": f"Analyzing the historical trend lines, the {target_col} did not show any month-over-month decline. The growth trend remains consistently positive.", "chart": None}
                
            biggest_drop_idx = drops['pct_change'].idxmin()
            drop_row = monthly.iloc[biggest_drop_idx]
            prev_row = monthly.iloc[biggest_drop_idx - 1]
            
            drop_date_str = drop_row[date_col].strftime('%B %Y')
            drop_val = drop_row[target_col]
            prev_val = prev_row[target_col]
            abs_drop = prev_val - drop_val
            pct_drop = abs(drop_row['pct_change'])
            
            text = (
                f"The most significant decline in {target_col} occurred in **{drop_date_str}**, where aggregate values "
                f"dropped from **${round(prev_val, 2)}** to **${round(drop_val, 2)}** (representing a decline of "
                f"**${round(abs_drop, 2)}** or **{round(pct_drop, 1)}%** compared to the previous period).\n\n"
            )
            
            # Segment drill-down (if product/category or region is available)
            drill_col = product_col or region_col
            if drill_col:
                t_df = temp_df
                d_month = drop_row[date_col].month
                d_year = drop_row[date_col].year
                p_month = prev_row[date_col].month
                p_year = prev_row[date_col].year
                
                prev_seg = t_df[(t_df[date_col].dt.month == p_month) & (t_df[date_col].dt.year == p_year)].groupby(drill_col)[target_col].sum()
                curr_seg = t_df[(t_df[date_col].dt.month == d_month) & (t_df[date_col].dt.year == d_year)].groupby(drill_col)[target_col].sum()
                
                diff = prev_seg - curr_seg
                if not diff.empty and diff.max() > 0:
                    worst_seg = diff.idxmax()
                    worst_drop = diff.max()
                    text += f"Further drill-down reveals this drop was primarily driven by the **'{worst_seg}'** segment (under column '{drill_col}'), which saw its revenue contract by **${round(worst_drop, 2)}**."
                    
            chart = {
                "type": "line",
                "labels": [d.strftime('%Y-%m-%d') for d in monthly[date_col].tolist()],
                "values": [float(x) for x in monthly[target_col].tolist()],
                "label": f"Monthly {target_col.capitalize()} Trend"
            }
            return {"text": text, "chart": chart}
            
        # 3. QUESTION: Predict / forecast future
        is_forecast_query = any(k in query_lower for k in ['predict', 'forecast', 'next month', 'future', 'projection'])
        if is_forecast_query:
            target_col = sales_col or profit_col
            if not target_col:
                return {"text": "I couldn't identify a metric column (like sales or profit) to project into future periods.", "chart": None}
            if not date_col:
                return {"text": "A date-time column is required to build a chronological trend projection model.", "chart": None}
                
            # Aggregate monthly
            temp_df = self.df.copy()
            temp_df[date_col] = pd.to_datetime(temp_df[date_col])
            monthly = temp_df.groupby(temp_df[date_col].dt.to_period('M'))[target_col].sum().reset_index()
            monthly[date_col] = monthly[date_col].dt.to_timestamp()
            
            if len(monthly) < 3:
                return {"text": "Insufficient data intervals (need at least 3 months of history) to train a trend model.", "chart": None}
                
            # Use simple linear trend for quick local predictions
            X = np.arange(len(monthly)).reshape(-1, 1)
            y = monthly[target_col].values
            from sklearn.linear_model import LinearRegression
            lr = LinearRegression()
            lr.fit(X, y)
            
            next_idx = len(monthly)
            pred_next = lr.predict([[next_idx]])[0]
            
            # Predict bounds
            residuals = y - lr.predict(X)
            std_err = residuals.std()
            lower = max(0.0, pred_next - 1.96 * std_err)
            upper = pred_next + 1.96 * std_err
            
            next_date = monthly[date_col].iloc[-1] + pd.DateOffset(months=1)
            next_date_str = next_date.strftime('%B %Y')
            
            text = (
                f"Using a linear regression model fit to your monthly historical records, the projected {target_col} for "
                f"**{next_date_str}** is **${round(pred_next, 2)}**. The 95% confidence interval spans from a lower limit of "
                f"**${round(lower, 2)}** to a maximum of **${round(upper, 2)}**."
            )
            
            # Chart includes historical + next month prediction
            labels = [d.strftime('%b %Y') for d in monthly[date_col].tolist()] + [next_date_str]
            values = [float(x) for x in y] + [float(pred_next)]
            
            chart = {
                "type": "bar",
                "labels": labels,
                "values": values,
                "label": f"Historical + Predicted {target_col.capitalize()}"
            }
            return {"text": text, "chart": chart}
            
        # 4. QUESTION: Which product performs poorly?
        is_poor_query = any(k in query_lower for k in ['poor', 'worst', 'lowest', 'least', 'bottom', 'low'])
        if is_poor_query:
            target_col = sales_col or profit_col
            drill_col = product_col or region_col
            
            if not drill_col:
                return {"text": "I couldn't locate a product name, category, or region column to evaluate bottom performances.", "chart": None}
            if not target_col:
                return {"text": "I couldn't identify a numeric sales or profit column to rank product outputs.", "chart": None}
                
            grouped = self.df.groupby(drill_col)[target_col].sum().reset_index()
            grouped = grouped.sort_values(by=target_col, ascending=True)
            
            worst_name = grouped.iloc[0][drill_col]
            worst_val = grouped.iloc[0][target_col]
            
            text = (
                f"Ranking the data columns in ascending order, the lowest-performing segment under '{drill_col}' "
                f"is **'{worst_name}'**, which generated a total {target_col} of only **${round(worst_val, 2)}**."
            )
            
            chart = {
                "type": "bar",
                "labels": [str(x) for x in grouped[drill_col].head(10).tolist()],
                "values": [float(x) for x in grouped[target_col].head(10).tolist()],
                "label": f"Bottom Performing {drill_col.capitalize()} ({target_col.capitalize()})"
            }
            return {"text": text, "chart": chart}
            
        # Default: Generate Business Insights summary
        else:
            insights = []
            row_cnt = len(self.df)
            insights.append(f"• Your dataset comprises **{row_cnt}** operational records spanning **{len(self.df.columns)}** columns.")
            
            if sales_col:
                tot_sales = self.df[sales_col].sum()
                avg_sales = self.df[sales_col].mean()
                insights.append(f"• Total aggregated {sales_col}: **${round(tot_sales, 2)}** (average transactions: **${round(avg_sales, 2)}**).")
                
            if profit_col:
                tot_profit = self.df[profit_col].sum()
                insights.append(f"• Total net profit: **${round(tot_profit, 2)}**.")
                
            if product_col and sales_col:
                top_p = self.df.groupby(product_col)[sales_col].sum().idxmax()
                insights.append(f"• Top contributing segment: **'{top_p}'** (ranking highest in aggregate revenue).")
                
            if date_col and sales_col:
                temp_df = self.df.copy()
                temp_df[date_col] = pd.to_datetime(temp_df[date_col])
                monthly = temp_df.set_index(date_col).resample('ME')[sales_col].sum()
                if len(monthly) >= 2:
                    change = (monthly.iloc[-1] - monthly.iloc[-2]) / monthly.iloc[-2] * 100
                    dir_str = "increase" if change > 0 else "decline"
                    insights.append(f"• Month-over-month growth rate: **{round(change, 1)}% {dir_str}** in the final period.")
                    
            text = "### Business Intelligence Summary Insights:\n\n" + "\n".join(insights)
            
            chart = None
            if product_col and sales_col:
                grouped = self.df.groupby(product_col)[sales_col].sum().reset_index().sort_values(by=sales_col, ascending=False).head(5)
                chart = {
                    "type": "bar",
                    "labels": [str(x) for x in grouped[product_col].tolist()],
                    "values": [float(x) for x in grouped[sales_col].tolist()],
                    "label": f"Top 5 {product_col.capitalize()} by Sales"
                }
                
            return {"text": text, "chart": chart}
