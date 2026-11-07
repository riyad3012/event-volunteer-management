# Event Volunteer Management System

A full-stack web application designed to simplify event organization and volunteer coordination through a centralized management platform.

## About the Project

The Event Volunteer Management System enables organizers to manage events and volunteers while allowing volunteers to register, participate in events, track attendance and download participation certificates.

## Features

### Volunteer
- User registration and login
- Browse and participate in events
- View volunteer dashboard
- Track attendance
- Download generated participation certificates in PDF format

### Organizer
- Organizer authentication
- Manage events and volunteers
- View volunteer information
- Mark and manage attendance
- Generate volunteer certificates

### Backend
- Flask-based application backend
- MySQL database integration
- REST API endpoints
- Session-based authentication

## Technologies Used

**Frontend**
- HTML5
- CSS3
- JavaScript

**Backend**
- Python
- Flask

**Database**
- MySQL

**Libraries**
- MySQL Connector
- Flask-CORS
- ReportLab
- Python-dotenv

## Project Structure

```text
event-volunteer-management/
│
├── frontend/
│   ├── admin.html
│   ├── admin.css
│   ├── admin.js
│   ├── dashboard.html
│   ├── dashboard.css
│   ├── dashboard.js
│   ├── organizer.html
│   ├── organizer.css
│   ├── organizer.js
│   ├── index.html
│   ├── script.js
│   └── style.css
│
├── app.py
├── test_register.py
├── requirements.txt
├── .env.example
└── .gitignore
```

## Installation and Setup

### 1. Clone the repository

```bash
git clone YOUR_REPOSITORY_URL
```

### 2. Navigate to the project folder

```bash
cd event-volunteer-management
```

### 3. Create a virtual environment

```bash
python -m venv venv
```

### 4. Activate the virtual environment

Windows:

```bash
venv\Scripts\activate
```

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

### 6. Configure environment variables

Create a `.env` file using `.env.example` as a reference.

Add your own Flask secret key and MySQL database credentials.

Never commit your actual `.env` file.

### 7. Configure the database

Create the required MySQL database and configure its connection details in `.env`.

### 8. Run the application

```bash
python app.py
```

## Security

- Environment variables are used for sensitive configuration.
- Database credentials are excluded from version control.
- Authentication is implemented for application access.

## Future Improvements

- Email notifications for event updates.
- Advanced event analytics.
- Improved volunteer scheduling.
- Cloud deployment and scalability.

## Developer

Riya D Souza

Artificial Intelligence and Machine Learning Undergraduate
