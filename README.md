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
The data folder needed to run the relevant Juypter Notebooks can be found in the Project Dropbox link: https://www.dropbox.com/scl/fo/ep4tu1jmr5tp62ndtcjdr/AFL5Bpywr5ATWJj3WHQ5zvE?rlkey=8aof2vux1ynegymdtychbq4qr&st=8i7mznt2&dl=0

### Running the functions
The code includes six functions: read_file_as_dataframe; select_columns; create_prompt_from_base; afrobarometer_second_person_base; afrobarometer_third_person_base; synthetic_interview. The functions are mainly designed to process Afrobarometer data (Ghana round 9) but could also be used to process other data files by adjusting some codes.

To create 'kitchen-sink' prompts, i.e. a series of demographic descriptions of a synthetic subject (e.g. "You are Ghanian and you live in... Answer the following question:..."), follow read_file_as_dataframe > select_columns > either afrobarometer_second_person_base (for second-person prompts "You are") or afrobarometer_third_person_base (for third-person prompts "She is") > create_prompt_from_base. To create 'synthetic interview' prompts, i.e. an interview format asking the LLM to answer the final question selected randomly, follow the aforementioned steps (using afrobarometer_second_person_base) and run the synthetic_interview function in the final step.

To generate a subsetted raw data file (a row for each respondent, with columns indicating the selected questions), simply run read_file_as_dataframe > select_columns, after setting the columns_demo, columns_resp, question_text variables (the descriptions of these variables can be found in the main file). The length of question_text should equal the sum of columns included in columns_demo and columns_resp. Run the following line after the aforementioned steps to rename the columns using the question_text variable.
```Python
df.columns = list(df.columns[:-len(question_text)]) + question_text
```
