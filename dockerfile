FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Using --no-cache-dir to save space
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Expose the port that Streamlit runs on (default is 8501)
EXPOSE 8501

# Define the command to run your Streamlit app
# The --server.port and --server.enableCORS are important for deployment
# --server.headless True is useful if you don't need a browser to open automatically
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
