# CPME246-Smart-Desk-Assistant-L2A-G5
CMPE 246 Mid-Term Project: Intelligent Focus Tracking &amp; Adaptive Study Support System

## Overview
This project implements an intelligent desk assistant that tracks user focus and provides adaptive study support through face recognition, environmental monitoring, and personalized user profiles.

## Project Structure

### Modules

#### DeepFace Integration
The project integrates **DeepFace**, a lightweight face recognition and facial attribute analysis framework, for advanced user identification and monitoring capabilities.

- **Location**: `modules/deepface/`
- **Purpose**: Provides state-of-the-art face recognition using models like VGG-Face, FaceNet, OpenFace, DeepFace, DeepID, ArcFace, Dlib, and more
- **Key Features**:
  - Face verification to authenticate users
  - Face recognition with database search capabilities
  - Facial attribute analysis (age, gender, emotion, race detection)
  - Support for multiple backend databases (PostgreSQL, MongoDB, Neo4j, pgvector, Pinecone)
  - High accuracy face detection and alignment

For detailed DeepFace documentation, see [`modules/deepface/README.md`](modules/deepface/README.md)

#### Face Recognition Module
- **Location**: `modules/face_recognition/`
- **Components**:
  - `User.py`: User profile management
  - `testmain.py`: Main testing and user registration interface
  - `ProfileTest.py`: Profile testing utilities

#### Environment Monitoring
- **Location**: `src/environment/`
- **Components**:
  - `environment_monitor.py`: Monitors desk environment conditions
  - `environment_logger.py`: Logs environmental data
  - `mock_hardware.py`: Hardware simulation for testing

## Installation

### Requirements
```bash
pip install -r requirements.txt
```

### DeepFace Setup
```bash
cd modules/deepface
pip install -r requirements.txt
```

## Configuration

### Database Path
The face recognition database path can be configured via environment variable:
```bash
# Windows
set CMPE246_DB_PATH=C:\path\to\your\database

# Linux/Mac
export CMPE246_DB_PATH=/path/to/your/database
```

If not set, the default path will be `~/CMPE246_DB` in your home directory.

## Usage

### Face Recognition Testing
```bash
python modules/face_recognition/testmain.py
```

### Environment Monitoring
```bash
python src/environment/test_env_system.py
```

## Features

- **User Authentication**: Face recognition-based user identification using DeepFace
- **Profile Management**: Personalized user profiles with custom focus/break times, lighting preferences, and audio settings
- **Environmental Monitoring**: Real-time monitoring of desk conditions
- **Guest Mode**: Quick access without registration
- **Multi-user Support**: Support for up to 4 registered users

## Documentation
- Project proposal: `docs/proposal/`
- Design documentation: `docs/design/`
- Deployment guides: `docs/deployment/`

## License
See [LICENSE](LICENSE) file for details.
