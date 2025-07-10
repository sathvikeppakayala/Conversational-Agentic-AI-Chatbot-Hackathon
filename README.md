# Conversational-Agentic-AI-Chatbot-Hackathon
# AUTO_CRPC

A web application for detecting and reporting scammers using Flask and MongoDB.

---

## Features

- ✅ User authentication (admin login)
- 📊 Dashboard with scammer and email statistics
- 🧾 PDF report generation using ReportLab
- 🔍 Search functionality for scammers and emails
- 🔌 RESTful API endpoints for data retrieval

---

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/AUTO_CRPC.git
cd AUTO_CRPC

### Install dependencies

```bash
pip install -r requirements.txt
```

### Set up environment

Create a `.env` file and add your MongoDB credentials:

```env
MONGO_URI=mongodb+srv://<username>:<password>@cluster.mongodb.net/<dbname>?retryWrites=true&w=majority
SECRET_KEY=your_secret_key
```

### Run the application

```bash
python main.py
# or
python app.py
```

---

## Usage

- Visit: [http://localhost:5000](http://localhost:5000)
- Login credentials:
  - **Username:** `admin`
  - **Password:** `aDmin@123`
- Use the dashboard to:
  - View scammer and email statistics
  - Search records
  - Generate PDF reports

---

## License

MIT License
