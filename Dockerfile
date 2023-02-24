# Use an official Python runtime as a parent image
FROM python:3.10-slim-buster

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

RUN chmod a+x run.sh

# Install any needed packages specified in requirements.txt
ENV FLIT_ROOT_INSTALL=1
RUN pip install flit
RUN flit install --deps production --pth-file

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
ENV ENVIRONMENT production

# Run the command to start the app
CMD ["./run.sh"]
# ENTRYPOINT [ "sleep", "infinity" ]