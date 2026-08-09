import unittest
import unittest.mock
import os
import pandas as pd
import numpy as np
from bson import ObjectId
from utilities.db_connection import get_db, initialize_db_indexes
from apps.automl.advisor import ModelAdvisor
from apps.ai_engine.personas import PersonaEngine
from apps.ai_engine.explainable_ai import ExplainableAI
from apps.nlp_query_engine.root_cause import RootCauseAnalysis
from apps.automl.monitoring import ModelMonitor
from apps.notifications.alert_engine import AlertEngine
from apps.automl.views import api_get_job_status

class TestAEDIPV2Features(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        initialize_db_indexes()
        
        # Setup mock project
        cls.project_id = ObjectId()
        cls.dataset_id = ObjectId()
        
    @classmethod
    def tearDownClass(cls):
        # Clean up any generated test records in MongoDB
        if cls.db is not None:
            cls.db.alerts.delete_many({"project_id": cls.project_id})
            cls.db.data_quality_reports.delete_many({"dataset_id": cls.dataset_id})
            cls.db.data_lineage.delete_many({"dataset_id": cls.dataset_id})
            cls.db.saved_queries.delete_many({"project_id": cls.project_id})
            cls.db.business_personas.delete_many({"dataset_id": cls.dataset_id})
            cls.db.predictions.delete_many({"project_id": cls.project_id})

    def test_01_model_advisor(self):
        """Unit Test: Verify Model Advisor suggests correct models for classification vs regression."""
        # Mock DataFrame
        df = pd.DataFrame({
            "Age": [25, 30, 35, 40, 45],
            "Salary": [50000, 60000, 70000, 80000, 90000],
            "Purchased": [0, 1, 0, 1, 0]
        })
        
        # Classification recommendations
        res_class = ModelAdvisor.generate_recommendations(df, target_col="Purchased", problem_type="classification")
        recs_class = res_class["models"]
        self.assertTrue(len(recs_class) > 0)
        self.assertIn("business_summary", res_class)
        
        # Regression recommendations
        res_regr = ModelAdvisor.generate_recommendations(df, target_col="Salary", problem_type="regression")
        recs_regr = res_regr["models"]
        self.assertTrue(len(recs_regr) > 0)
        self.assertIn("business_summary", res_regr)

    def test_02_customer_persona_segmentation(self):
        """Unit Test: Verify Persona Engine segments numerical features and labels clusters."""
        df = pd.DataFrame({
            "CustomerID": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
            "Sales": [100.0, 500.0, 1000.0, 120.0, 600.0, 1100.0, 90.0, 450.0, 950.0, 80.0, 520.0, 1050.0],
            "Transactions": [1, 5, 10, 2, 6, 11, 1, 4, 9, 1, 5, 10]
        })
        
        segmentation = PersonaEngine.segment_entities(df, num_clusters=3)
        self.assertTrue(segmentation.get("segmented"))
        self.assertIn("target_kpi_indicator", segmentation)
        self.assertTrue(len(segmentation["segments"]) > 0)
        
        # Check first segment has recommendations and name
        first_seg = segmentation["segments"][0]
        self.assertIn("persona_name", first_seg)
        self.assertTrue(len(first_seg["recommendations"]) > 0)

    def test_03_explainable_ai_lfp(self):
        """Unit Test: Verify Local Feature Perturbation XAI generates positive/negative feature drivers."""
        # Simple mock model simulating a model
        class MockModel:
            def predict(self, X):
                # Target is 2 * Feature1 - Feature2
                return 2 * X["Feature1"] - X["Feature2"]
                
        model = MockModel()
        row_df = pd.DataFrame({
            "Feature1": [10.0],
            "Feature2": [5.0]
        })
        encoders = {}
        summary_stats = {
            "Feature1": {"mean": 8.0, "std": 2.0, "median": 8.0},
            "Feature2": {"mean": 4.0, "std": 1.0, "median": 4.0}
        }
        
        explanation = ExplainableAI.explain_prediction(
            model, encoders, row_df, summary_stats, problem_type="regression"
        )
        
        self.assertIn("prediction_value", explanation)
        self.assertIn("human_readable_explanation", explanation)
        self.assertTrue(len(explanation["positive_drivers"]) > 0 or len(explanation["negative_drivers"]) > 0)

    def test_04_root_cause_analysis(self):
        """Unit Test: Verify Root Cause Analysis detects monthly KPI drops and highlights worst segment."""
        dates = pd.date_range(start="2026-01-01", periods=60, freq="D")
        sales = np.random.normal(loc=100, scale=10, size=60)
        # Force a major drop in month 2
        sales[30:] = sales[30:] * 0.5
        
        df = pd.DataFrame({
            "Date": dates,
            "Sales": sales,
            "Region": np.random.choice(["East", "West"], size=60)
        })
        
        analysis = RootCauseAnalysis.analyze_kpi_drop(df, target_col="Sales", date_col="Date")
        self.assertTrue(analysis.get("success"))
        self.assertTrue(analysis.get("decline_detected"))
        self.assertIn("root_cause_explanation", analysis)
        self.assertTrue(len(analysis["drilldown_dimensions"]) > 0)

    def test_05_model_monitor_drift(self):
        """Integration Test: Verify ModelMonitor detects feature drift via KS-test."""
        np.random.seed(42)
        # Create normal training data
        df_train = pd.DataFrame({
            "Feature1": np.random.normal(loc=10.0, scale=1.0, size=100),
            "Feature2": np.random.normal(loc=5.0, scale=0.5, size=100)
        })
        
        # Create drifted inference data (higher mean for Feature1)
        df_infer = pd.DataFrame({
            "Feature1": np.random.normal(loc=15.0, scale=1.0, size=100),
            "Feature2": np.random.normal(loc=5.0, scale=0.5, size=100)
        })

        
        drift_results = ModelMonitor.calculate_drift(df_train, df_infer, features=["Feature1", "Feature2"])
        
        self.assertIn("drift_percentage", drift_results)
        self.assertIn("Feature1", drift_results["drifted_features"], "Feature1 should be detected as drifted.")
        self.assertNotIn("Feature2", drift_results["drifted_features"], "Feature2 should not be detected as drifted.")

    def test_06_alert_engine_scanner(self):
        """Integration Test: Verify AlertEngine generates warning entries for data quality drops."""
        if self.db is None:
            self.skipTest("Database offline.")
            
        # Write a mock low quality dataset doc to trigger alert
        self.db.datasets.insert_one({
            "_id": self.dataset_id,
            "project_id": self.project_id,
            "filename": "qa_bad_quality_dataset.csv",
            "data_quality_score": 45.0, # Will trigger High/Critical quality alert
            "created_at": pd.Timestamp.now()
        })
        
        new_alerts = AlertEngine.scan_for_alerts(str(self.project_id))
        self.assertTrue(new_alerts > 0, "At least 1 data quality alert should have been written to MongoDB.")
        
        # Fetch alert to verify severity
        alert = self.db.alerts.find_one({"project_id": self.project_id, "event": "Data Quality Degradation"})
        self.assertIsNotNone(alert)
        self.assertEqual(alert["severity"], "CRITICAL")
        self.assertFalse(alert["is_read"])

    @unittest.mock.patch("utilities.decorators.get_current_user")
    def test_07_api_get_business_personas(self, mock_get_user):
        """Integration Test: Verify business personas view endpoint runs segmentation."""
        if self.db is None:
            self.skipTest("Database offline.")
            
        mock_get_user.return_value = {
            "id": "6a76069b3de160c4ea28e4ee",
            "role": "analyst",
            "organization_id": "6a76069b3de160c4ea28e4ed",
            "workspace_id": "6a76069b3de160c4ea28e4ef"
        }
        
        ds_id = ObjectId()
        # Save a mock dataset referencing the real Bike Sales excel file on disk
        file_path = os.path.join("media", "datasets", "Bike_Sales_Prepare_Lab_3.4.7_v1.xlsx")
        self.db.datasets.insert_one({
            "_id": ds_id,
            "project_id": self.project_id,
            "filename": "Bike_Sales_Prepare_Lab_3.4.7.xlsx",
            "file_path": file_path,
            "version": 1,
            "data_quality_score": 95.0,
            "created_at": pd.Timestamp.now()
        })
        
        from django.test import RequestFactory
        from apps.ai_engine.personas import api_get_business_personas
        
        factory = RequestFactory()
        request = factory.get(f"/ai/api/personas/{ds_id}/")
        
        try:
            res = api_get_business_personas(request, dataset_id=str(ds_id))
            self.assertEqual(res.status_code, 200)
            
            # Verify result is successfully written to database
            saved_record = self.db.business_personas.find_one({"dataset_id": ds_id})
            self.assertIsNotNone(saved_record)
            self.assertTrue(saved_record["segmentation"]["segmented"])
        finally:
            self.db.datasets.delete_one({"_id": ds_id})
            self.db.business_personas.delete_one({"dataset_id": ds_id})

    @unittest.mock.patch("utilities.decorators.get_current_user")
    def test_08_visualization_data_api(self, mock_get_user):
        """Integration Test: Verify visualization API generates chart series and correlation matrices."""
        if self.db is None:
            self.skipTest("Database offline.")
            
        mock_get_user.return_value = {
            "id": "6a76069b3de160c4ea28e4ee",
            "role": "analyst"
        }
        
        ds_id = ObjectId()
        file_path = os.path.join("media", "datasets", "Bike_Sales_Prepare_Lab_3.4.7_v1.xlsx")
        self.db.datasets.insert_one({
            "_id": ds_id,
            "project_id": self.project_id,
            "filename": "Bike_Sales.xlsx",
            "file_path": file_path,
            "data_quality_score": 90.0,
            "created_at": pd.Timestamp.now()
        })
        
        from django.test import RequestFactory
        from apps.dashboard.views import api_get_visualization_data
        
        factory = RequestFactory()
        
        try:
            # 1. Test Heatmap
            req = factory.get(f"/api/visualization/data/?dataset_id={ds_id}&chart_type=heatmap")
            res = api_get_visualization_data(req)
            self.assertEqual(res.status_code, 200)
            
            # 2. Test Bar Chart Aggregation
            req_bar = factory.get(f"/api/visualization/data/?dataset_id={ds_id}&chart_type=bar&x_col=Country&y_col=Revenue&aggregation=SUM")
            res_bar = api_get_visualization_data(req_bar)
            self.assertEqual(res_bar.status_code, 200)
        finally:
            self.db.datasets.delete_one({"_id": ds_id})

    @unittest.mock.patch("utilities.decorators.get_current_user")
    def test_09_custom_dashboard_widget_crud(self, mock_get_user):
        """Integration Test: Verify saving, listing, and deleting custom pinned dashboard widgets."""
        if self.db is None:
            self.skipTest("Database offline.")
            
        mock_get_user.return_value = {
            "id": "6a76069b3de160c4ea28e4ee",
            "role": "analyst"
        }
        
        from django.test import RequestFactory
        from apps.dashboard.views import api_save_dashboard_widget, api_get_workspace_dashboard, api_delete_dashboard_widget
        import json
        
        factory = RequestFactory()
        
        # Save widget
        save_req = factory.post(
            "/api/dashboard/widget/save/",
            data=json.dumps({
                "project_id": str(self.project_id),
                "title": "Test KPI Widget",
                "widget_type": "chart",
                "config": {"chart_type": "bar"}
            }),
            content_type="application/json"
        )
        save_res = api_save_dashboard_widget(save_req)
        self.assertEqual(save_res.status_code, 200)
        widget_id = json.loads(save_res.content)["widget_id"]
        
        # List widgets
        list_req = factory.get(f"/api/dashboard/widget/list/{self.project_id}/")
        list_res = api_get_workspace_dashboard(list_req, project_id=str(self.project_id))
        self.assertEqual(list_res.status_code, 200)
        widgets = json.loads(list_res.content)["widgets"]
        self.assertTrue(any(w["_id"] == widget_id for w in widgets))
        
        # Delete widget
        del_req = factory.post(
            "/api/dashboard/widget/delete/",
            data=json.dumps({"widget_id": widget_id}),
            content_type="application/json"
        )
        del_res = api_delete_dashboard_widget(del_req)
        self.assertEqual(del_res.status_code, 200)

    @unittest.mock.patch("apps.automl.tasks.train_automl_models_task")
    def test_10_auto_retrain_trigger(self, mock_retrain_task):
        """Integration Test: Verify AlertEngine triggers auto retrain on low quality score dataset."""
        if self.db is None:
            self.skipTest("Database offline.")
            
        ds_id = ObjectId()
        model_id = ObjectId()
        
        self.db.datasets.insert_one({
            "_id": ds_id,
            "project_id": self.project_id,
            "filename": "critical_bad_data.csv",
            "data_quality_score": 40.0, # CRITICAL quality score <60
            "created_at": pd.Timestamp.now()
        })
        self.db.models.insert_one({
            "_id": model_id,
            "project_id": self.project_id,
            "dataset_id": ds_id,
            "name": "Random Forest (Classification)",
            "problem_type": "classification",
            "target_column": "Target",
            "created_at": pd.Timestamp.now()
        })
        
        try:
            from apps.notifications.alert_engine import AlertEngine
            AlertEngine.scan_for_alerts(str(self.project_id))
            
            # Verify background retraining task was called
            self.assertTrue(mock_retrain_task.called)
            
            # Verify lineage log entry
            lineage = self.db.data_lineage.find_one({"dataset_id": ds_id, "operation": "AUTO_RETRAIN_TRIGGERED"})
            self.assertIsNotNone(lineage)
        finally:
            self.db.datasets.delete_one({"_id": ds_id})
            self.db.models.delete_one({"_id": model_id})
            self.db.data_lineage.delete_many({"dataset_id": ds_id})

    @unittest.mock.patch("utilities.decorators.get_current_user")
    def test_11_automl_live_progress_tracking(self, mock_get_user):
        """Integration Test: Verify AutoML live progress tracking job creation and status API."""
        if self.db is None:
            self.skipTest("Database offline.")

        mock_get_user.return_value = {
            "id": "6a76069b3de160c4ea28e4ee",
            "role": "analyst"
        }

        job_id = str(ObjectId())
        ds_id = str(ObjectId())

        self.db.automl_jobs.insert_one({
            "_id": ObjectId(job_id),
            "project_id": self.project_id,
            "dataset_id": ObjectId(ds_id),
            "target_column": "Sales",
            "problem_type": "regression",
            "status": "training",
            "progress_pct": 45,
            "current_step": "Fitting Gradient Boosting Regressor (3/8)...",
            "active_model": "Gradient Boosting",
            "created_at": pd.Timestamp.now()
        })

        try:
            url = f"/automl/api/job/status/{job_id}/"
            from django.test import RequestFactory
            req = RequestFactory().get(url)
            
            res = api_get_job_status(req, job_id)
            self.assertEqual(res.status_code, 200)
            
            import json
            data = json.loads(res.content)
            self.assertIn("job", data)
            self.assertEqual(data["job"]["progress_pct"], 45)
            self.assertEqual(data["job"]["active_model"], "Gradient Boosting")
        finally:
            self.db.automl_jobs.delete_one({"_id": ObjectId(job_id)})

    def test_12_automl_custom_model_selection(self):
        """Integration Test: Verify selected_models filters candidate algorithms in AutoML task."""
        if self.db is None:
            self.skipTest("Database offline.")
            
        ds_id = ObjectId()
        file_path = os.path.join("media", "datasets", "sales_test_sample.csv")
        df_mock = pd.DataFrame({"Feature1": np.arange(1, 51), "Target": np.arange(10, 510, 10)})
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df_mock.to_csv(file_path, index=False)
        
        self.db.datasets.insert_one({
            "_id": ds_id,
            "project_id": self.project_id,
            "filename": "sales_test_sample.csv",
            "file_path": file_path,
            "data_quality_score": 95.0,
            "created_at": pd.Timestamp.now()
        })
        
        try:
            from apps.automl.tasks import train_automl_models_task
            job_id = str(ObjectId())
            
            # Execute with only Random Forest selected
            train_automl_models_task(
                str(self.project_id),
                str(ds_id),
                "Target",
                "regression",
                str(ObjectId()),
                job_id=job_id,
                selected_models=["Random Forest"]
            )
            
            model = self.db.models.find_one({"project_id": self.project_id, "dataset_id": ds_id})
            self.assertIsNotNone(model)
            self.assertEqual(len(model["leaderboard"]), 1)
            self.assertEqual(model["leaderboard"][0]["model_name"], "Random Forest")
        finally:
            self.db.datasets.delete_one({"_id": ds_id})
            self.db.models.delete_many({"dataset_id": ds_id})
            self.db.automl_jobs.delete_one({"_id": ObjectId(job_id)})
            if os.path.exists(file_path):
                os.remove(file_path)

if __name__ == '__main__':
    unittest.main()

