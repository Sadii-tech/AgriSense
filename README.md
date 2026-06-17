# AgriSense
# 🌱 AgriSense AI

## AI-Based Agricultural Quality Assessment System

### Fruit Condition Prediction & Plant Disease Detection Using Computer Vision

![Python](https://img.shields.io/badge/Python-3.x-blue)
![Django](https://img.shields.io/badge/Django-Web%20Framework-green)
![TensorFlow](https://img.shields.io/badge/TensorFlow-AI-orange)
![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-red)
![License](https://img.shields.io/badge/License-Educational-lightgrey)

---

## 📖 Project Overview

AgriSense AI is an AI-powered agricultural monitoring and quality assessment system designed to assist farmers in identifying fruit spoilage and plant diseases at an early stage.

The system combines Computer Vision, Deep Learning, and Web Technologies to provide automated agricultural analysis through image-based predictions. Using trained MobileNetV3 models, the platform can classify fruit quality, detect plant diseases, estimate confidence levels, and provide actionable recommendations.

The project aims to reduce crop losses, improve productivity, and support smart farming practices through accessible AI technology.

---

## 🎯 Problem Statement

Traditional agricultural inspection methods rely heavily on manual observation, making them:

* Time-consuming
* Labor-intensive
* Subjective and inconsistent
* Difficult to scale for large farms

Most existing AI solutions focus on a single agricultural problem and provide only image-level predictions.

AgriSense AI addresses these challenges by integrating:

* Fruit quality assessment
* Plant disease detection
* Confidence-aware predictions
* Historical monitoring and analytics
* Decision-support recommendations

into one intelligent platform.

---

## ✨ Key Features

### 🍎 Fruit Quality Classification

Classifies fruits into:

* Fresh
* Semi-Rotten
* Rotten

Provides:

* Prediction label
* Confidence score
* Reliability assessment

---

### 🌿 Plant Disease Detection

Detects diseases from leaf images.

Provides:

* Disease name
* Prediction confidence
* Severity estimation

---

### 📊 Progress Tracking

Tracks historical predictions and visualizes:

* Disease progression
* Fruit spoilage trends
* Condition deterioration over time

---

### 💡 Recommendation Engine

Generates decision-support suggestions such as:

* Monitor affected crops
* Isolate infected plants
* Apply preventive treatment
* Schedule follow-up inspections

---

## 🏗 System Architecture

### Input Layer

* Camera Images
* Uploaded Fruit Images
* Uploaded Leaf Images

### Processing Layer

* Image Resizing
* Normalization
* Data Augmentation
* Feature Extraction

### AI Layer

* MobileNetV3 Classification Models
* Confidence Scoring
* Reliability Threshold Evaluation

### Database Layer

* SQLite Database
* Prediction Records
* Historical Tracking

### Presentation Layer

* Django Web Application
* Interactive Dashboard
* Result Visualization

---

## 🧠 Machine Learning Techniques

The project utilizes:

* Convolutional Neural Networks (CNN)
* Transfer Learning
* MobileNetV3
* Image Augmentation
* Softmax Confidence Scoring
* Threshold-Based Reliability Filtering

---

## 🛠 Technology Stack

| Category             | Technology                               |
| -------------------- | ---------------------------------------- |
| Operating System     | Windows 10 / 11                          |
| Programming Language | Python                                   |
| Backend Framework    | Django (DWF)                             |
| Frontend             | HTML5, CSS3, Bootstrap 5, JavaScript ES6 |
| AI Framework         | TensorFlow                               |
| Deep Learning Model  | MobileNetV3                              |
| Image Processing     | OpenCV, Pillow (PIL)                     |
| Database             | SQLite                                   |
| Model Training       | Jupyter Notebook (Anaconda)              |
| Version Control      | Git & GitHub                             |
| API Testing          | Postman                                  |
| Dataset Source       | Kaggle                                   |
| Code Editor          | Visual Studio Code                       |

---

## 📂 Project Structure

```text
AgriSense-AI/
│
├── dataset/
├── models/
├── notebooks/
├── static/
│   ├── css/
│   ├── js/
│   └── images/
│
├── templates/
│
├── prediction/
│
├── media/
│
├── db.sqlite3
├── manage.py
├── requirements.txt
└── README.md
```

---

## ⚙ Installation

### Clone Repository

```bash
git clone https://github.com/yourusername/AgriSense-AI.git
cd AgriSense-AI
```

### Create Virtual Environment

```bash
python -m venv venv
```

### Activate Environment

```bash
venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Migrations

```bash
python manage.py migrate
```

### Start Development Server

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000
```

---

## 📈 Expected Outcomes

* Early disease identification
* Reduced crop losses
* Improved agricultural decision-making
* Enhanced crop quality monitoring
* Practical AI deployment in agriculture

---

## 🔮 Future Improvements

* Mobile Application
* Real-Time Camera Monitoring
* Multi-Crop Disease Detection
* Edge AI Deployment
* Cloud Synchronization
* Farmer Alert Notifications
* Yield Prediction Module

---

## 📸 Screenshots

Add screenshots here:

* Home Page
* Fruit Quality Prediction
* Disease Detection Results
* Analytics Dashboard

---

## 👩‍💻 Author

**Sadia**
BS Computer Science

Areas of Interest:

* Artificial Intelligence
* Machine Learning
* Computer Vision
* Web Development
* Smart Agriculture Solutions

---

## 📜 License

This project is developed for educational and research purposes.

---

### 🌱 AgriSense AI

### Empowering Smart Agriculture Through Artificial Intelligence
