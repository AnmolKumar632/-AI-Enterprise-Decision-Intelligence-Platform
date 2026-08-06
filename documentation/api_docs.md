# REST API Documentation - AEDIP

## 1. Authentication Endpoints

### 1.1 User Registration
*   **Endpoint:** `POST /auth/api/register/`
*   **Payload:**
    ```json
    {
      "email": "user@company.com",
      "password": "securepassword",
      "first_name": "Jane",
      "last_name": "Doe",
      "role": "analyst"
    }
    ```
*   **Response (201 Created):**
    ```json
    {
      "message": "User registered successfully. Please verify your email.",
      "verification_token": "a83fb9c8-11a2-4fb3-bb02-e283fac92a83",
      "user_id": "64c92b23cf1a8e1ab307ef11"
    }
    ```

### 1.2 User Login
*   **Endpoint:** `POST /auth/api/login/`
*   **Payload:**
    ```json
    {
      "email": "user@company.com",
      "password": "securepassword"
    }
    ```
*   **Response (200 OK):**
    ```json
    {
      "message": "Login successful.",
      "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "user": {
        "id": "64c92b23cf1a8e1ab307ef11",
        "email": "user@company.com",
        "first_name": "Jane",
        "last_name": "Doe",
        "role": "analyst"
      }
    }
    ```

---

## 2. Dataset Management Endpoints

### 2.1 Upload Dataset
*   **Endpoint:** `POST /datasets/api/upload/`
*   **Headers:** `Authorization: Bearer <token>`
*   **Multipart Body:**
    *   `file`: (file object, CSV/Excel)
    *   `project_id`: `64c92b9acf1a8e1ab307ef12`
*   **Response (201 Created):**
    ```json
    {
      "message": "Dataset uploaded successfully.",
      "dataset_id": "64c92bc4cf1a8e1ab307ef13",
      "filename": "sales_data.csv",
      "quality_score": 85.5,
      "row_count": 150,
      "column_count": 8
    }
    ```

### 2.2 Clean Dataset
*   **Endpoint:** `POST /datasets/api/clean/<dataset_id>/`
*   **Headers:** `Authorization: Bearer <token>`
*   **Response (200 OK):**
    ```json
    {
      "message": "Dataset cleaned successfully.",
      "original_quality_score": 85.5,
      "cleaned_quality_score": 98.2,
      "cleaning_summary": {
        "removed_duplicates": 2,
        "imputed_missing_columns": {"Profit": 3, "Quantity": 1},
        "outliers_action": {"total_outliers_detected": 4, "action": "Clipped extreme outliers..."},
        "timestamp": "2026-08-06T18:05:00.123456"
      }
    }
    ```

---

## 3. AutoML Engine Endpoints

### 3.1 Trigger Model Training
*   **Endpoint:** `POST /automl/api/train/`
*   **Headers:** `Authorization: Bearer <token>`
*   **Payload:**
    ```json
    {
      "dataset_id": "64c92bc4cf1a8e1ab307ef13",
      "target_column": "Profit"
    }
    ```
*   **Response (202 Accepted):**
    ```json
    {
      "message": "AutoML training triggered successfully.",
      "task_id": "b304fb98-0c0b-468a-9893-18fac8bb9cc1",
      "detected_problem_type": "regression"
    }
    ```

### 3.2 Batch Predictions
*   **Endpoint:** `POST /automl/api/predict/`
*   **Headers:** `Authorization: Bearer <token>`
*   **Payload:**
    ```json
    {
      "model_id": "64c92c84cf1a8e1ab307ef15",
      "dataset_id": "64c92bc4cf1a8e1ab307ef13"
    }
    ```
*   **Response (200 OK):**
    ```json
    {
      "message": "Predictions completed.",
      "prediction_id": "64c92d0ccf1a8e1ab307ef19",
      "sample_predictions": [45.2, 120.5, 33.1],
      "explainability_preview": [
        {
          "row_index": 0,
          "prediction": 45.2,
          "explanations": {"Quantity": 12.5, "Unit_Price": 32.1}
        }
      ]
    }
    ```

---

## 4. NLP Conversational Queries

### 4.1 Execute Analytics Question
*   **Endpoint:** `POST /nlp/api/query/`
*   **Headers:** `Authorization: Bearer <token>`
*   **Payload:**
    ```json
    {
      "dataset_id": "64c92bc4cf1a8e1ab307ef13",
      "query": "Why did sales decrease?"
    }
    ```
*   **Response (200 OK):**
    ```json
    {
      "query": "Why did sales decrease?",
      "text_response": "The largest decline in Sales occurred in June 2026, where values dropped from $45,000 to $32,000...",
      "chart_response": {
        "type": "line",
        "labels": ["2026-05-31", "2026-06-30"],
        "values": [45000.0, 32000.0],
        "label": "Monthly Sales Trend"
      }
    }
    ```
