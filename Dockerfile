# Use an official lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Expose the Flask port
EXPOSE 5000

# Optional: Set default environment variables
ENV FLASK_APP=app.py

# Run the app 
CMD ["python", "app.py"]
