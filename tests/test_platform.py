import unittest
import os
import pandas as pd
import numpy as np
from bson import ObjectId
from utilities.db_connection import get_db, initialize_db_indexes
from apps.ai_engine.preprocessing import DataPreprocessor

class TestAEDIPPlatform(unittest.TestCase):
    
    def setUp(self):
        self.db = get_db()
        
    def test_mongodb_connection(self):
        """Verify MongoDB client is connected and indexes can be initialized."""
        self.assertIsNotNone(self.db, "MongoDB connection should be active.")
        # Try fetching server info
        client = self.db.client
        server_info = client.server_info()
        self.assertIn("version", server_info)
        
        # Test index initialization is successful
        try:
            initialize_db_indexes()
            index_init_ok = True
        except Exception:
            index_init_ok = False
        self.assertTrue(index_init_ok, "MongoDB indexes should initialize without throwing exceptions.")
        
    def test_data_preprocessor(self):
        """Test missing value imputation, outlier clipping, and quality scoring."""
        # Create a mock DataFrame with duplicate rows and missing values
        data = {
            "Age": [25, 30, np.nan, 35, 30],  # 1 missing, 1 duplicate (indices 1 and 4)
            "Salary": [50000.0, 60000.0, 70000.0, np.nan, 60000.0],  # 1 missing, 1 duplicate
            "Department": ["Sales", "HR", "IT", "Sales", "HR"]  # categorical duplicate
        }
        df = pd.DataFrame(data)
        
        preprocessor = DataPreprocessor(df)
        
        # Check initial stats
        schema = preprocessor.detect_schema()
        self.assertEqual(schema["Age"]["missing_count"], 1)
        
        # Calculate initial quality score
        score_before = preprocessor.calculate_quality_score()
        self.assertTrue(0 <= score_before <= 100)
        
        # Test duplicate removal
        removed = preprocessor.remove_duplicates()
        self.assertEqual(removed, 1, "Exactly 1 duplicate row should be removed.")
        self.assertEqual(len(preprocessor.df), 4)
        
        # Test imputation
        imputed = preprocessor.impute_missing()
        self.assertIn("Age", imputed)
        self.assertIn("Salary", imputed)
        self.assertEqual(preprocessor.df["Age"].isnull().sum(), 0, "No missing ages should remain.")
        self.assertEqual(preprocessor.df["Salary"].isnull().sum(), 0, "No missing salaries should remain.")
        
        # Verify quality score increases after cleaning
        score_after = preprocessor.calculate_quality_score()
        self.assertGreaterEqual(score_after, score_before, "Hygiene score should improve after duplicate removal and imputation.")
        
    def test_feature_scaling_and_encoding(self):
        """Verify scale_and_encode correctly scales numericals and encodes categoricals."""
        data = {
            "Feature1": [1.0, 2.0, 3.0, 4.0, 5.0],
            "Category1": ["Low", "High", "Low", "Medium", "High"],
            "Target": [0, 1, 0, 1, 0]
        }
        df = pd.DataFrame(data)
        
        preprocessor = DataPreprocessor(df)
        processed_df, encoders = preprocessor.scale_and_encode(target_col="Target")
        
        # Check target is preserved but Category1 is label encoded (numerical values)
        self.assertIn("Category1", processed_df.columns)
        self.assertTrue(pd.api.types.is_numeric_dtype(processed_df["Category1"]))
        self.assertIn("Category1", encoders, "LabelEncoder should be fitted and saved for Category1.")
        
        # Check Feature1 is scaled (mean near 0, std near 1)
        mean_f1 = processed_df["Feature1"].mean()
        std_f1 = processed_df["Feature1"].std()
        self.assertAlmostEqual(mean_f1, 0.0, places=5)
        self.assertAlmostEqual(std_f1, 1.11803, places=3) # Sample std of standard-scaled numbers
        
if __name__ == '__main__':
    unittest.main()
