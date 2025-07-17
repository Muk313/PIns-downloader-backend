# Stage 1: Build Stage - Use an official Playwright image with Python
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy AS builder

# Set the working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2: Runtime Stage
# Use a smaller base image for the final runtime if possible, or keep the Playwright image
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set the working directory
WORKDIR /app

# Copy installed Python packages from the builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Copy Playwright browser binaries (already present in this base image, but explicit copy for clarity)
# This line is technically not needed if the base image is the same as builder, but good practice for multi-stage
COPY --from=builder /ms-playwright /ms-playwright

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Run the application
CMD ["bash", "-c", "python3 -m gunicorn --bind 0.0.0.0:5000 src.main:app"]
