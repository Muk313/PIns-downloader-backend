# Use the official Python image with Playwright pre-installed
FROM mcr.microsoft.com/playwright/python:v1.49.1-jammy

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Set the command to run the application
CMD ["python", "src/main.py"]

