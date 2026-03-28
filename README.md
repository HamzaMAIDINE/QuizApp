# QuizApp

A powerful, dynamic web-based quiz application built with Flask. The application features a dedicated Teacher portal to easily create and manage quizzes, and a Student portal to provide an intuitive exam-taking experience.

## ✨ Features

### 👩‍🏫 For Teachers
* **Quick Setup:** Secure initial setup via the `/setup` route to create your admin account (includes an account recovery code system).
* **Comprehensive Dashboard:** An easy-to-use interface to manage quizzes, activate/deactivate them dynamically, and archive older content.
* **Quiz Creation:** Build quizzes with multiple-choice questions, set time limits (in minutes), and manage an unlimited number of options per question.
* **Analytics & Results:** Track student performance in real-time. Filter results by class, and sort by name, score, or timestamp.

### 👨‍🎓 For Students
* **Seamless Access:** Join active quizzes effortlessly without complex registrations.
* **Dynamic Exam Environment:** Automatic randomization of both questions and options.
* **Enforced Integrity:** Server-side time tracking enforces strict time limits with an automatic grace period cutoff.

## 🛠️ Tech Stack
* **Backend:** Python 3, Flask
* **Database:** SQLite (via `Flask-SQLAlchemy` & `Flask-Migrate`)
* **Security & Optimization:** `Flask-WTF` (CSRF), `Werkzeug` (Password Hashing), `Flask-Limiter` (Rate Limiting)
* **Live Features:** `Flask-SocketIO`
* **Containerization:** Docker & Docker Compose

---

## 🚀 Installation & Setup

You can run this application either locally on your machine or inside a Docker container.

### Option A: Local Run (Windows, macOS, Linux)

1. **Clone or Download** the project to your local machine.
2. **Setup your environment:**
   Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux / macOS
   source venv/bin/activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Start the server:**
   You can use the provided quick-start scripts to automatically activate the environment and run the server.
   * **Windows:** Simply double-click `run_server.bat` or run it in the command line.
   * **Linux/macOS:** Run the shell script: `./run_server.sh`
5. **Access the App:** Open a web browser and go to `http://localhost:5000`. On your first visit, you will be redirected to the `/setup` page to register the Teacher account.

### Option B: Docker Compose

If you use Docker, you can securely spin up the entire application with a single command:

1. **Start the containers** in detached mode:
   ```bash
   docker-compose up --build -d
   ```
2. **Access the App:** Navigate to `http://localhost:5000`.
   *(Note: The SQLite database automatically persists via a mapped volume in the `/instance` directory).*

---

## 📂 Project Structure

- `app.py`: Flask application factory, server initialization, and configuration.
- `models.py`: Database models (`Teacher`, `Quiz`, `Question`, `Option`, `StudentResult`).
- `routes.py`: Core routing logic, grouping both Teacher and Student workflows.
- `extensions.py`: Centralized initialization for third-party Flask libraries.
- `docker-compose.yml` / `Dockerfile`: Docker configurations for isolated deployments.
- `run_server.bat` / `run_server.sh`: Cross-platform helper scripts to boot the local server.
