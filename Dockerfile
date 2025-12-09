# Use the official Playwright image (Pre-loaded with Python, Chromium & Dependencies)
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# Set the working directory inside the container
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Run the application
CMD ["python", "app.py"]