import numpy as np
import pandas as pd

class ExplainableAI:
    @staticmethod
    def explain_prediction(model, encoders: dict, row_df: pd.DataFrame, train_summary_stats: dict, problem_type: str) -> dict:
        """Calculate feature contributions for a single prediction row using Local Feature Perturbation (LFP)."""
        feature_names = list(row_df.columns)
        
        # 1. Base prediction
        if problem_type == 'classification':
            try:
                base_prob = model.predict_proba(row_df)[0]
                base_val = float(base_prob.max())
                base_class = int(base_prob.argmax())
            except Exception:
                # If predict_proba fails, fallback to standard predict
                base_val = float(model.predict(row_df)[0])
                base_class = int(base_val)
        else:
            base_val = float(model.predict(row_df)[0])

        contributions = {}
        
        # 2. Perturb each feature and measure prediction delta
        for col in feature_names:
            perturbed_df = row_df.copy()
            
            # Decide how to perturb based on column type
            # Check training summary stats to get standard deviations/medians for numericals
            stats = train_summary_stats.get(col, {"mean": 0.0, "std": 1.0, "median": 0.0})
            
            val = row_df.iloc[0][col]
            
            # Perform perturbation
            if col in encoders:
                # Categorical: Perturb by changing to a different category value (shifting code)
                le = encoders[col]
                # If it's encoded, the value is an integer code. Switch to another code.
                current_code = int(val)
                num_classes = len(le.classes_)
                perturbed_val = (current_code + 1) % num_classes if num_classes > 1 else current_code
            else:
                # Numerical: Perturb by adding 1 standard deviation or shifting by mean
                std = stats.get("std", 1.0)
                if std == 0 or np.isnan(std):
                    std = 1.0
                perturbed_val = val + std

            perturbed_df.loc[perturbed_df.index[0], col] = perturbed_val
            
            # Predict with perturbed features
            if problem_type == 'classification':
                try:
                    p_prob = model.predict_proba(perturbed_df)[0]
                    # Measure change in the base class's probability
                    p_val = float(p_prob[base_class])
                    delta = base_val - p_val
                except Exception:
                    p_pred = float(model.predict(perturbed_df)[0])
                    delta = base_val - p_pred
            else:
                p_pred = float(model.predict(perturbed_df)[0])
                delta = base_val - p_pred
                
            contributions[col] = delta

        # Normalize contributions to form percentage impact scores
        total_delta = sum(abs(v) for v in contributions.values())
        if total_delta > 0:
            impact_scores = {k: round((v / total_delta) * 100, 2) for k, v in contributions.items()}
        else:
            impact_scores = {k: 0.0 for k in feature_names}

        # Divide into positive and negative drivers relative to prediction direction
        positive_factors = []
        negative_factors = []
        
        for feature, score in impact_scores.items():
            val_display = row_df.iloc[0][feature]
            # Convert back encoded categoricals to original label strings for readability
            if feature in encoders:
                le = encoders[feature]
                code = int(val_display)
                if code < len(le.classes_):
                    val_display = le.classes_[code]

            factor_detail = {
                "feature": feature,
                "value": str(val_display),
                "impact": abs(score)
            }
            if score >= 0:
                positive_factors.append(factor_detail)
            else:
                negative_factors.append(factor_detail)

        # Sort factors by impact score
        positive_factors = sorted(positive_factors, key=lambda x: x['impact'], reverse=True)
        negative_factors = sorted(negative_factors, key=lambda x: x['impact'], reverse=True)

        # Generate human-readable explanation
        top_pos = positive_factors[0]['feature'] if positive_factors else "None"
        explanation = (
            f"The prediction output is primarily driven by feature **'{top_pos}'** (contributing positively)."
        )
        if negative_factors:
            explanation += f" Features like **'{negative_factors[0]['feature']}'** acted as countervailing negative pressures."

        return {
            "prediction_value": base_val,
            "positive_drivers": positive_factors[:5],
            "negative_drivers": negative_factors[:5],
            "human_readable_explanation": explanation
        }
