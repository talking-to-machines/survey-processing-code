# Talking to Machines - Survey Processing Code

This repository contains the source code for processing survey data for Talking to Machines.

## Getting Started

Follow these steps to set up the project locally.

### Prerequisites

- Python 3.11 or higher
- Git

### Clone the Repository
```bash
git clone https://github.com/talking-to-machines/survey-processing-code.git
cd survey-processing-code
```

### Create a Virtual Environment
```bash
# On Windows
python -m venv venv

# On macOS/Linux
python3 -m venv venv
```

Activate the Virtual Environment
```bash
# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Deactivate the Virtual Environment
```bash
deactivate
```

## Usage
The code is primarily designed to process Afrobarometer data (Ghana round 9) but could also be used to process other survey data files by adjusting some parts. The raw data file for Afrobarometer Ghana round 9 can be found in the following link: https://www.afrobarometer.org/data/data-sets/

The jupyter notebook explains the pipelines for processing survey data files.