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
        
        # Identify common business columns
        sales_col = self._find_column(['sales', 'revenue', 'turnover'], default=None)
        profit_col = self._find_column(['profit', 'margin', 'gain'], default=None)
        region_col = self._find_column(['region', 'state', 'country', 'city'], default=None)
        product_col = self._find_column(['product', 'item', 'sku', 'category'], default=None)
        date_col = self._find_column(['date', 'month', 'year', 'timestamp'], default=None)
        
        # 1. QUESTION: Which region has maximum profit/sales?
        if 'region' in query_lower and ('max' in query_lower or 'highest' in query_lower or 'best' in query_lower or 'most' in query_lower):
            target_col = profit_col or sales_col
            if not region_col:
                return {"text": "I couldn't identify a region/geography column in your dataset.", "chart": None}
            if not target_col:
                return {"text": "I couldn't identify a profit or sales metric column in your dataset.", "chart": None}
                
            grouped = self.df.groupby(region_col)[target_col].sum().reset_index()
            grouped = grouped.sort_values(by=target_col, ascending=False)
            
            top_region = grouped.iloc[0][region_col]
            top_val = grouped.iloc[0][target_col]
            total_val = grouped[target_col].sum()
            pct = (top_val / total_val * 100) if total_val > 0 else 0
            
            text = f"The **'{top_region}'** region generated the highest performance with a total {target_col} of **${round(top_val, 2)}** (representing **{round(pct, 1)}%** of the total ${round(total_val, 2)} across all regions)."
            
            chart = {
                "type": "bar",
                "labels": [str(x) for x in grouped[region_col].tolist()],
                "values": [float(x) for x in grouped[target_col].tolist()],
                "label": f"Total {target_col.capitalize()} by Region"
            }
            return {"text": text, "chart": chart}
            
        # 2. QUESTION: Why did sales decrease?
        elif 'decrease' in query_lower or 'drop' in query_lower or 'decline' in query_lower or 'why did' in query_lower:
            target_col = sales_col or profit_col
            if not target_col:
                return {"text": "I couldn't identify a sales or profit column to analyze trends.", "chart": None}
            if not date_col:
                return {"text": "I couldn't identify a date or time column to calculate monthly drop.", "chart": None}
                
            # Aggregate monthly
            temp_df = self.df.copy()
            temp_df[date_col] = pd.to_datetime(temp_df[date_col])
            monthly = temp_df.set_index(date_col).resample('ME')[target_col].sum().reset_index()
            
            if len(monthly) < 2:
                return {"text": "The dataset contains insufficient monthly historical intervals to calculate drops.", "chart": None}
                
            monthly['pct_change'] = monthly[target_col].pct_change() * 100
            drops = monthly[monthly['pct_change'] < 0]
            
            if drops.empty:
                return {"text": f"Analyzing the historical trend, {target_col} did not show any monthly drop. The trend is consistently positive.", "chart": None}
                
            biggest_drop_idx = drops['pct_change'].idxmin()
            drop_row = monthly.iloc[biggest_drop_idx]
            prev_row = monthly.iloc[biggest_drop_idx - 1]
            
            drop_date_str = drop_row[date_col].strftime('%B %Y')
            drop_val = drop_row[target_col]
            prev_val = prev_row[target_col]
            abs_drop = prev_val - drop_val
            pct_drop = abs(drop_row['pct_change'])
            
            text = f"The largest decline in {target_col} occurred in **{drop_date_str}**, where values dropped from **${round(prev_val, 2)}** to **${round(drop_val, 2)}** (a drop of **${round(abs_drop, 2)}** or **{round(pct_drop, 1)}%**).\n\n"
            
            # Segment drill-down (if product/category or region is available)
            drill_col = product_col or region_col
            if drill_col:
                # Compare drop month with prev month in segments
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
                    text += f"Drill-down analysis reveals that this decline was heavily driven by the **'{worst_seg}'** {drill_col}, which fell by **${round(worst_drop, 2)}** compared to the prior period."
                    
            chart = {
                "type": "line",
                "labels": [d.strftime('%Y-%m-%d') for d in monthly[date_col].tolist()],
                "values": [float(x) for x in monthly[target_col].tolist()],
                "label": f"Monthly {target_col.capitalize()} Trend"
            }
            return {"text": text, "chart": chart}
            
        # 3. QUESTION: Predict / forecast future
        elif 'predict' in query_lower or 'forecast' in query_lower or 'next month' in query_lower:
            target_col = sales_col or profit_col
            if not target_col:
                return {"text": "I couldn't identify a metric column (sales/profit) to predict.", "chart": None}
            if not date_col:
                return {"text": "I need a date column to build a predictive forecast.", "chart": None}
                
            # Aggregate monthly
            temp_df = self.df.copy()
            temp_df[date_col] = pd.to_datetime(temp_df[date_col])
            monthly = temp_df.groupby(temp_df[date_col].dt.to_period('M'))[target_col].sum().reset_index()
            monthly[date_col] = monthly[date_col].dt.to_timestamp()
            
            if len(monthly) < 3:
                return {"text": "Insufficient historical points to train a prediction model. Need at least 3 months.", "chart": None}
                
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
            
            text = f"Based on a linear regression trend fit to historical data, the predicted {target_col} for **{next_date_str}** is **${round(pred_next, 2)}** (with a 95% confidence interval ranging from **${round(lower, 2)}** to **${round(upper, 2)}**)."
            
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
        elif 'poor' in query_lower or 'worst' in query_lower or 'lowest' in query_lower or 'least' in query_lower:
            target_col = sales_col or profit_col
            drill_col = product_col or region_col
            
            if not drill_col:
                return {"text": "I couldn't identify any product, item, or category columns in this dataset.", "chart": None}
            if not target_col:
                return {"text": "I couldn't identify a sales or profit metric to evaluate performance.", "chart": None}
                
            grouped = self.df.groupby(drill_col)[target_col].sum().reset_index()
            grouped = grouped.sort_values(by=target_col, ascending=True)
            
            worst_name = grouped.iloc[0][drill_col]
            worst_val = grouped.iloc[0][target_col]
            
            text = f"The lowest-performing {drill_col} is **'{worst_name}'**, generating a total {target_col} of only **${round(worst_val, 2)}**."
            
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
            # Calculate total metrics
            row_cnt = len(self.df)
            insights.append(f"• Dataset consists of **{row_cnt}** business transaction records and **{len(self.df.columns)}** columns.")
            
            if sales_col:
                tot_sales = self.df[sales_col].sum()
                avg_sales = self.df[sales_col].mean()
                insights.append(f"• Total cumulative {sales_col} generated: **${round(tot_sales, 2)}** (average per transaction: **${round(avg_sales, 2)}**).")
                
            if profit_col:
                tot_profit = self.df[profit_col].sum()
                insights.append(f"• Total cumulative net profit: **${round(tot_profit, 2)}**.")
                
            if product_col and sales_col:
                top_p = self.df.groupby(product_col)[sales_col].sum().idxmax()
                insights.append(f"• Top contributing product segment: **'{top_p}'**.")
                
            if date_col and sales_col:
                # growth
                temp_df = self.df.copy()
                temp_df[date_col] = pd.to_datetime(temp_df[date_col])
                monthly = temp_df.set_index(date_col).resample('ME')[sales_col].sum()
                if len(monthly) >= 2:
                    change = (monthly.iloc[-1] - monthly.iloc[-2]) / monthly.iloc[-2] * 100
                    dir_str = "increase" if change > 0 else "decline"
                    insights.append(f"• Month-over-month sales growth: **{round(change, 1)}% {dir_str}** in the final period.")
                    
            text = "### Automated Business Insights Summary:\n\n" + "\n".join(insights)
            
            # Simple chart
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
