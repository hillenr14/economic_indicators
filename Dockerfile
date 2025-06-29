# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Expose the port that the Flask app runs on
EXPOSE 5001

# Define environment variables for MySQL connection
ENV MYSQL_HOST=db
ENV MYSQL_USER=hillenr
ENV MYSQL_PASSWORD=robert14
ENV MYSQL_DB=historical_data

# Run the Flask application
CMD ["python", "app.py"]
