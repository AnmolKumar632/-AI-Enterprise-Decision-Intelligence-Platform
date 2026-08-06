import unittest
import os
import pandas as pd
import numpy as np
import json
from bson import ObjectId
from utilities.db_connection import get_db, initialize_db_indexes
from utilities.decorators import get_current_user
from apps.ai_engine.preprocessing import DataPreprocessor
from apps.nlp_query_engine.interpreter import NLQueryInterpreter
from apps.report_generator.generator import ReportGenerator

class TestAEDIPSystemE2E(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Set up testing context and clean target collections."""
        cls.db = get_db()
        initialize_db_indexes()
        
        # Mock user details
        cls.test_email = "e2e_tester@enterprise.com"
        cls.db.users.delete_many({"email": cls.test_email})
        
        # Insert test user
        cls.user_doc = {
            "email": cls.test_email,
            "password_hash": "pbkdf2_sha256$mock_hash_string",
            "first_name": "E2E",
            "last_name": "Tester",
            "role": "analyst",
            "is_verified": True
        }
        res = cls.db.users.insert_one(cls.user_doc)
        cls.user_id = str(res.inserted_id)
        
        # Mock project
        cls.project_doc = {
            "owner_id": ObjectId(cls.user_id),
            "name": "E2E Staging Project",
            "description": "Integration and UAT workspace validation"
        }
        p_res = cls.db.projects.insert_one(cls.project_doc)
        cls.project_id = str(p_res.inserted_id)
        
    @classmethod
    def tearDownClass(cls):
        """Clean up testing docs."""
        cls.db.users.delete_many({"email": cls.test_email})
        cls.db.projects.delete_many({"_id": ObjectId(cls.project_id)})
        
    def test_01_database_and_workspace_integrity(self):
        """UAT: Verify workspace collection references and DB connectivity."""
        project = self.db.projects.find_one({"_id": ObjectId(self.project_id)})
        self.assertIsNotNone(project)
        self.assertEqual(project["name"], "E2E Staging Project")
        self.assertEqual(str(project["owner_id"]), self.user_id)
        
    def test_02_data_preprocessor_pipeline(self):
        """Component: Verify preprocessor drops duplicates, fills NaNs, and scores data."""
        # Index 1 and 2 are exact duplicate rows
        data = {
            "Date": ["2026-01-01", "2026-01-02", "2026-01-02", "2026-01-03", "2026-01-05"],
            "Sales": [100.0, 150.0, 150.0, np.nan, 150.0],
            "Category": ["Electronics", "Furniture", "Furniture", "Electronics", "Furniture"]
        }
        df = pd.DataFrame(data)
        preprocessor = DataPreprocessor(df)
        
        # Test cleaning flow
        dups_removed = preprocessor.remove_duplicates()
        self.assertEqual(dups_removed, 1, "Duplicate row should be dropped.")
        
        imputed = preprocessor.impute_missing()
        self.assertIn("Sales", imputed)
        self.assertEqual(imputed["Sales"], 1, "One NaN in Sales should be filled.")
        
        quality_score = preprocessor.calculate_quality_score()
        self.assertTrue(quality_score > 70.0, f"Quality score should be robust: {quality_score}")
        
    def test_03_automl_problem_detection(self):
        """Component: Verify AutoML pipeline detects problem type and trains regressors."""
        data = {
            "Age": [25, 32, 45, 51, 23, 38, 41, 29, 36, 48],
            "Salary": [50000.0, 62000.0, 95000.0, 110000.0, 48000.0, 78000.0, 85000.0, 59000.0, 72000.0, 92000.0],
            "Purchased": [0, 0, 1, 1, 0, 1, 1, 0, 0, 1]
        }
        df = pd.DataFrame(data)
        
        # Test problem type heuristics
        target_continuous = "Salary"
        target_discrete = "Purchased"
        
        # Verify continuous is classified as regression
        distinct_cont = df[target_continuous].nunique()
        self.assertTrue(distinct_cont > 5)
        
        # Verify discrete is classification
        distinct_disc = df[target_discrete].nunique()
        self.assertEqual(distinct_disc, 2)
        
    def test_04_nlp_query_interpretation(self):
        """Integration: Verify NLP heuristics engine handles keywords and aggregates."""
        data = {
            "Date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "Sales": [100, 200, 150, 300],
            "Region": ["North", "North", "South", "South"],
            "Product": ["Laptop", "Phone", "Laptop", "Phone"]
        }
        df = pd.DataFrame(data)
        interpreter = NLQueryInterpreter(df)
        
        # Test Region Max Sales query
        res = interpreter.interpret("Which region has maximum sales?")
        self.assertIn("text", res)
        self.assertIn("chart", res)
        self.assertEqual(res["chart"]["type"], "bar")
        self.assertIn("South", res["text"], "South should be returned as the top sales region.")
        
    def test_05_executive_report_builder(self):
        """Integration: Verify Report Generator builds PDF files."""
        # Setup output folder and generator
        output_dir = os.path.join("media", "reports")
        os.makedirs(output_dir, exist_ok=True)
        
        generator = ReportGenerator(output_dir)
        pdf_file = generator.generate_pdf(
            project_name="Test Workspace",
            dataset_name="sales_data.csv",
            quality_score=95.0,
            model_name="Random Forest",
            model_metrics={"r2": 0.941},
            forecast_summary="ARIMA time series projection detects an upward sales trajectory.",
            anomaly_summary="Isolation Forest detected 3 outliers.",
            recommendations=["Focus sales effort on high performing regions."]
        )
        
        self.assertTrue(os.path.exists(pdf_file), "PDF report file must be written to disk.")
        if os.path.exists(pdf_file):
            os.remove(pdf_file)

if __name__ == '__main__':
    unittest.main()
