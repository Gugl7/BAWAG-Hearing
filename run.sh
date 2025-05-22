echo "Building the docker image for the Streamlit app..."

sudo docker build -t bawag-app .

echo "Running the docker container for the Streamlit app..."

sudo docker run -p 8501:8501 bawag-app