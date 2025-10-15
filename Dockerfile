FROM python:3.10.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gfortran \
    libpq-dev \
    build-essential \
    cmake \
    git \
    libssl-dev \
    libffi-dev \
    python3-dev \
    libopenblas-dev \
    liblapack-dev \
    pkg-config \
    locales \
    && rm -rf /var/lib/apt/lists/*

# Set locale to avoid encoding issues during compilation
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen
ENV LANG en_US.UTF-8  
ENV LANGUAGE en_US:en  
ENV LC_ALL en_US.UTF-8

# Install SEAL library system-wide to /usr/local (improves caching and reuse across builds)
RUN git clone https://github.com/microsoft/SEAL.git /tmp/SEAL && \
    cd /tmp/SEAL && \
    git checkout v4.1.1 && \
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DSEAL_USE_CXX17=ON && \
    cmake --build build && \
    cmake --install build --prefix /usr/local && \
    rm -rf /tmp/SEAL  # Clean up SEAL source files to reduce image size

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel
# Set cmake policy to handle version compatibility
ENV CMAKE_POLICY_VERSION_MINIMUM=3.5
RUN pip install Cython==0.29.36

RUN pip install -r requirements.txt --verbose

# Copy project
COPY . /app/

# Install the src library in editable mode
RUN pip install -e /app/src

# Collect static files
RUN python /app/cti4bc_backend/manage.py collectstatic --noinput

EXPOSE 8000

# Run the Django application using the development server
CMD ["python", "/app/cti4bc_backend/manage.py", "runserver", "0.0.0.0:8000"]