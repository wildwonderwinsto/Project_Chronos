# Use the UPDATED official Playwright image matching your installed version
FROM mcr.microsoft.com/playwright/python:v1.56.0-jammy

# Set the working directory inside the container
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Install Tesseract OCR for CAPTCHA solving
RUN apt-get update && apt-get install -y tesseract-ocr && rm -rf /var/lib/apt/lists/*

# Run the application
CMD ["python", "app.py"]