# Installation & Operations Guide - AEDIP

## 1. System Requirements
*   **Operating System:** Windows 10/11, macOS, or Linux.
*   **Python:** Python 3.12+ (tested on Python 3.14.2).
*   **Database:** MongoDB Community Server (v6.x or newer) running locally or via Docker.
*   **Web Server / Proxy:** Gunicorn + Nginx (for production deployments).

## 2. Local Setup Instructions

### Step 2.1: Clone Repository & Prepare Workspace
Clone or place the project files inside your target workspace directory:
```bash
cd "c:\Users\csp\OneDrive\Documents\AI Enterprise Decision Intelligence"
```

### Step 2.2: Setup Python Virtual Environment
Initialize a local Python virtual environment to manage dependencies locally and prevent pollution of system globals:
```bash
# On Windows
python -m venv .venv
.venv\Scripts\activate

# On macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2.3: Install System Dependencies
Install necessary Django, machine learning, and document compilation libraries:
```bash
pip install -r requirements.txt
```

### Step 2.4: Configure Services
AEDIP requires a running instance of MongoDB on port `27017`.
*   **Option A (Native MongoDB):** Ensure the native MongoDB service is started on your local system:
    ```powershell
    # Windows PowerShell check
    Get-Service -Name MongoDB
    ```
*   **Option B (Docker Compose):** If Docker Desktop is running, launch services in the background:
    ```bash
    docker-compose up -d
    ```

---

## 3. Operations & Startup

### Step 3.1: Initialize Database Migrations
Initialize standard internal Django sessions and administrator tables on the local SQLite file:
```bash
python manage.py migrate
```

### Step 3.2: Launch Local Web Server
Start the Django development server:
```bash
python manage.py run-server 0.0.0.0:8000
```
Open a browser and navigate to: `http://127.0.0.1:8000/`.

---

## 4. Platform Testing & Demonstration
To demonstrate and evaluate the functional capabilities of the platform:
1.  Navigate to `http://127.0.0.1:8000/auth/register-page/` and create an analyst account.
2.  Click the simulated email verification link provided in the registration success card.
3.  Login to the platform.
4.  Create a project workspace.
5.  In the **Datasets** panel, upload one of the pre-generated sample spreadsheets from `media/samples/sales_data.csv`.
6.  Execute preprocessing, explore the charts, run AutoML pipelines, ask NLP questions, and download the compiled report sheets!
