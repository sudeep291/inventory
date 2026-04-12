# Use Lean Python 3.11 image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Step 1: Install Python dependencies (Faster Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 2: Copy App (Project Slender: 65MB+ removed)
COPY . .

# Step 3: Deployment Config
EXPOSE 5000

# Step 4: Start System
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app", "--timeout", "120"]
