import pandas as pd
import numpy as np
import pyreadstat
import rdata
import os

def read_file_as_dataframe(file_path: str) -> pd.DataFrame:
	"""
	Convert the raw survey data and read as pandas dataframe
  
  Parameters:
    filepath (str): The path to the survey data file.

  Returns:
    pd.DataFrame: The survey data.
	"""

  # detect file type
  _, file_extension = os.path.splitext(file_path)

  if file_extension.lower() == '.csv':
    df = pd.read_csv(file_path)
  elif file_extension.lower() == ".tsv":
    df = pd.read_csv(file_path, sep="\t")
  elif file_extension.lower() in ['.xls', '.xlsx']:
    df = pd.read_excel(file_path)
  elif file_extension.lower() == '.rdata':
    df = rdata.read_rda(file_path)
    keys = list(df.keys())
    df = df[keys[0]]
  elif file_extension.lower() == '.sav':
    df, meta = pyreadstat.read_sav(file_path, apply_value_formats=True, formats_as_category=False)
  else:
    raise ValueError("Unsupported file type: " + file_extension)

  return df

def select_columns(raw_data: pd.DataFrame, columns_demo: str, columns_resp: str) -> pd.DataFrame:
  """
  Select relevant columns from the downloaded survey data using the returned dataframe from the read_file_as_dataframe function
  
  Parameters:
    raw_data (pd.DataFrame): The raw dataset returned from the read_file_as_dataframe function
    columns_demo (str): The names of selected columns for demographics in a single string divided by comma (e.g. "Q1, Q100, Q101, Q2, Q94, Q95, Q84A, Q93A, Q93B")
    columns_resp (str): The names of selected columns for substantives in a single string divided by comma
  
  Returns:
    pd.DataFrame: The survey data with selected columns
  """

  # create ID column for each respondent
  raw_data['ID_'] = range(1, len(raw_data) + 1)

  # create column vector from column id strings
  columns = columns_demo.split(", ") + columns_resp.split(", ")
  columns.insert(0, 'ID_')

  # select columns
  df = raw_data[columns]

  # clean curly quotation marks and apostrophes
  df = df.replace({'“': "'", '”': "'", '’': "'"}, regex=True)

  return df

def kitchen_sink_prompt(df: pd.DataFrame, columns_demo: str, columns_resp: str, question_text: list) -> pd.DataFrame:
  """
  Create prompts for asking substantive questions to LLMs using the returned dataframe from either afrobarometer_second_person_base or afrobarometer_third_person_base

  Parameters:
    df (pd.DataFrame): The cleaned survey data returned from a custom cleaning function (e.g. afrobarometer_second_person_base, afrobarometer_third_person_base)
    columns_demo (str): The names of selected columns for demographics in a single string divided by comma (e.g. "Q1, Q100, Q101, Q2, Q94, Q95, Q84A, Q93A, Q93B")
    columns_resp (str): The names of selected columns for substantives in a single string divided by comma
    question_text (list): The list of substantive questions; required to have the same number of items as columns included in columns_resp and in the same order
  
  Returns:
    pd.DataFrame: The final survey data for LLM application
  """

  # make a response level variable for each substantive question
  columns_resp = columns_resp.split(", ")
  for col in columns_resp:
    column = df[col]
    # avoid error for selecting more than a single column
    if isinstance(column, pd.DataFrame):
      column = column.iloc[:, 0]
    # filter out don't knows and the like
    mask = ~column.str.contains('refused|not applicable|don\'t know|no contact|do not know', case=False, na=False)
    # apply the mask, drop duplicates, sort and then concatenate with a semicolon
    unique_values = column[mask].dropna().unique()
    unique_values.sort()
    df[f'response_{col}'] = '; '.join(unique_values)

  # make a row for each question (pivot_longer)
  df = pd.melt(df,
               id_vars=[col for col in df.columns if col not in columns_resp],
               value_vars=columns_resp,
               var_name='Question',
               value_name='Response')

  df['Text'] = np.select([df['Question'] == q for q in columns_resp], question_text, default="")

  # create prompt texts from question text and response levels
  df['Response_level'] = df.apply(lambda row: row[f"response_{row['Question']}"] if f"response_{row['Question']}" in row else 'N/A', axis=1)
  df['Prompt'] = df.apply(lambda row: f"{row['demo_base']} '{row['Text']}' from the following responses: '{row['Response_level']}'", axis=1)
  df = df.drop(columns=['Text', *df.filter(regex='response_Q').columns])

  # Select specific columns (assuming you listed all columns you need explicitly)
  columns_demo = columns_demo.split(", ")
  columns_demo.insert(0, 'ID_')
  columns_demo = columns_demo + ['demo_base', 'Question', 'Response_level', 'Prompt', 'Response']
  df = df[columns_demo]

  # Filtering rows based on a condition
  df = df[~df['Response'].isin(['Not applicable', 'Not Applicable', 'Refused to Answer',
                                'No contact', 'Don\'t Know', 'Don\'t know', 'Refused', 'Refused to answer',
                                'Do not know'])]

  return df

def afrobarometer_second_person_base(df: pd.DataFrame) -> pd.DataFrame:
  """
  Reorganise demographic variables from the afrobarometer data (Ghana round 9) and create the base for second-person ("You are") prompts using the dataframe returned from select_columns
  Since some demographic variables that would be useful when creating prompts (e.g. employment status, etc) are not organised in such a way as to allow direct pasting when creating prompts, this function re-organises these variables prior to generating prompts
  Reorganised variables are: employment; electricity; mobile phone; health clinic; party support; voting intention

  Paramters:
    df (pd.DataFrame): The survey data with selected variables returned from select_columns

  Returns:
    pd.DataFrame: The survey data prepared for prompt creation (goes to kitchen_sink_prompt)
  """

  # employment
  # conditions are order dependent
  empl_condlist = [df['Q93A'] == 'No (not looking)',
                   df['Q93A'] == 'No (looking)',
                   df['Q93A'] == 'Yes, part time',
                   df['Q93A'] == 'Yes, full time']
  empl_choicelist = ["You are unemployed and not looking for a job.",
                     "You are unemployed and looking for a job.",
                     "You have a part-time job.",
                     "You have a full-time job."]
  df['empl'] = np.select(empl_condlist, empl_choicelist, default="")

  # electricity
  elec_condlist = [df['Q92A'] == 'No',
                   df['Q92A'] == 'Yes']
  elec_choicelist = ["You don't live in a home with electricity connection.",
                     "You live in a home with electricity connection."]
  df['elec'] = np.select(elec_condlist, elec_choicelist, default="")

  # mobile phone
  mobile_condlist = [(df['Q90F'] == 'Yes (personally owns)') & (df['Q90G'] == 'No (Does not have internet access)'),
                     (df['Q90F'] == 'Yes (personally owns)') & (df['Q90G'] == 'Yes (Have internet)'),
                     df['Q90F'] == 'Yes (personally owns)',
                     df['Q90F'] == 'Someone else in household owns',
                     df['Q90F'] == 'No, no one in the household owns']
  mobile_choicelist = ["You personally own a mobile phone but your phone doesn't have an Internet access.",
                       "You personally own a mobile phone and your phone has an Internet access.",
                       "You personally own a mobile phone.",
                       "You don't personally own a mobile phone but someone else in the household owns a mobile phone.",
                       "No one in your household owns a mobile phone."]
  df['mobile'] = np.select(mobile_condlist, mobile_choicelist, default="")

  # nearby health clinic
  clinic_condlist = [df['EA_FAC_D'] == 'No',
                     df['EA_FAC_D'] == 'Yes']
  clinic_choicelist = ["There's no health clinic near home.",
                       "There's a health clinic near home."]
  df['clinic'] = np.select(clinic_condlist, clinic_choicelist, default="")

  # party
  party_condlist = [(df['Q89A'] == "Yes (feels close to a party)") & (~df['Q89B'].isin(['Refused', "Don't know"])),
                    df['Q89A'] == "Yes (feels close to a party)",
                    df['Q89A'] == "No (does NOT feel close to ANY party)",
                    df['Q89A'] == "Don't know"]
  party_choicelist = [("You feel close to " + df['Q89B'] + "."),
                      "You have a political party you feel close.",
                      "You don't feel close to any particular party.",
                      "You don't know if you feel close to any particular party."]
  df['party'] = np.select(party_condlist, party_choicelist, default="")

  # voting intention
  vote_condlist = [df['Q96']  == "Would not vote",
                   df['Q96'] == "Don't know",
                   df['Q96'] == "Refused to answer",
                   df['Q96'] != "Refused to answer"]
  vote_choicelist = ["You would not vote if a presidential election is held tomorrow.",
                     "You don't know who you would vote for if a presidential election is held tomorrow.",
                     "",
                     ("The political party of your preferred presidential candidate is " + df['Q96'] + ".")]
  df['vote'] = np.select(vote_condlist, vote_choicelist, default="")

  # create base prompt for each row
  df['demo_base'] = ("You are Ghanaian and you live in a " + df['URBRUR'] +
                     " area in the " + df['REGION'] +
                     " region of Ghana. You are " + df['Q1'].astype(int).astype(str) +
                     " years old. You are a " + df['Q100'] +
                     " and your race is " + df['Q101'] +
                     ". The primary language you speak at home is " + df['Q2'] +
                     ". Your highest level of education is " + df['Q94'] +
                     ". Your religion is " + df['Q95'] +
                     ". You identify as " + df['Q84A'] + ". " +
                     df['empl'] +
                     " Your last occupation is " + df['Q93B'] +
                     ". Your household's main source of water is " + df['Q91A'] +
                     ". " + df['elec'] +
                     " " + df['mobile'] +
                     " " + df['clinic'] +
                     " You feel " + df['Q4B'] +
                     " about your present living condition. " + df['party'] +
                     " " + df['vote'] +
                     " Answer the question")

  # reconstruct priority variable
  conditions = [df['Q45PT1'].isin(['Health', 'AIDS', 'COVID-19', 'Sickness / Disease']),
                df['Q45PT1'].isin(['Nothing/ no problems', 'Refused', "Don't know"]),
                ~df['Q45PT1'].isin(['Nothing/ no problems', 'Refused', "Don't know"])]
  choices = ["Health-related issues such as health, sickness/disease, COVID-19 and AIDS",
             df['Q45PT1'],
             "Issues other than health such as the economy, food/agriculture, infrastructure, public services, country's governance and climate"]
  df['Q45PT1'] = np.select(conditions, choices, default=df['Q45PT1'])

  return df

def afrobarometer_third_person_base(df: pd.DataFrame) -> pd.DataFrame:
  """
  Reorganise demographic variables from the afrobarometer data (Ghana round 9) and create the base for third-person ("She is") prompts using the dataframe returned from select_columns
  Since some demographic variables that would be useful when creating prompts (e.g. employment status, etc) are not organised in such a way as to allow direct pasting when creating prompts, this function re-organises these variables prior to generating prompts
  Reorganised variables are: employment; electricity; mobile phone; health clinic; party support; voting intention
  Paramters:
    df (pd.DataFrame): The survey data with selected variables returned from select_columns

  Returns:
    pd.DataFrame: The survey data prepared for prompt creation (goes to kitchen_sink_prompt)
  """

  gender = [df['Q100'] == 'Woman',
            df['Q100'] == 'Man']
  df['pronoun_nom'] = np.select(gender, ["She", "He"], default = "")
  df['pronoun_pos'] = np.select(gender, ["Her", "His"], default = "")

  # employment
  # conditions are order dependent
  empl_condlist = [df['Q93A'] == 'No (not looking)',
                   df['Q93A'] == 'No (looking)',
                   df['Q93A'] == 'Yes, part time',
                   df['Q93A'] == 'Yes, full time']
  empl_choicelist = [(df['pronoun_nom'] + " is unemployed and not looking for a job."),
                     (df['pronoun_nom'] + " is unemployed and looking for a job."),
                     (df['pronoun_nom'] + " has a part-time job."),
                     (df['pronoun_nom'] + " has a full-time job.")]
  df['empl'] = np.select(empl_condlist, empl_choicelist, default="")

  # electricity
  elec_condlist = [df['Q92A'] == 'No',
                   df['Q92A'] == 'Yes']
  elec_choicelist = [(df['pronoun_nom'] + " doesn't live in a home with electricity connection."),
                     (df['pronoun_nom'] + " lives in a home with electricity connection.")]
  df['elec'] = np.select(elec_condlist, elec_choicelist, default="")

  # mobile phone
  mobile_condlist = [(df['Q90F'] == 'Yes (personally owns)') & (df['Q90G'] == 'No (Does not have internet access)'),
                     (df['Q90F'] == 'Yes (personally owns)') & (df['Q90G'] == 'Yes (Have internet)'),
                     df['Q90F'] == 'Yes (personally owns)',
                     df['Q90F'] == 'Someone else in household owns',
                     df['Q90F'] == 'No, no one in the household owns']
  mobile_choicelist = [(df['pronoun_nom'] + " personally owns a mobile phone but " + df['pronoun_pos'] + " phone doesn't have an Internet access."),
                       (df['pronoun_nom'] + " personally owns a mobile phone and " + df['pronoun_pos'] + " phone has an Internet access."),
                       (df['pronoun_nom'] + " personally owns a mobile phone."),
                       (df['pronoun_nom'] + " doesn't personally own a mobile phone but someone else in the household owns a mobile phone."),
                       ("No one in "  + df['pronoun_pos'] +  " household owns a mobile phone.")]
  df['mobile'] = np.select(mobile_condlist, mobile_choicelist, default="")

  # nearby health clinic
  clinic_condlist = [df['EA_FAC_D'] == 'No',
                     df['EA_FAC_D'] == 'Yes']
  clinic_choicelist = [("There's no health clinic near " + df['pronoun_pos'] + " home."),
                       ("There's a health clinic near " + df['pronoun_pos'] + " home.")]
  df['clinic'] = np.select(clinic_condlist, clinic_choicelist, default="")

  # party
  party_condlist = [(df['Q89A'] == "Yes (feels close to a party)") & (~df['Q89B'].isin(['Refused', "Don't know"])),
                    df['Q89A'] == "Yes (feels close to a party)",
                    df['Q89A'] == "No (does NOT feel close to ANY party)",
                    df['Q89A'] == "Don't know"]
  party_choicelist = [(df['pronoun_nom'] + " feels close to " + df['Q89B'] + "."),
                      (df['pronoun_nom'] + " has a political party " + df['pronoun_nom'] + " feels close."),
                      (df['pronoun_nom'] + " doesn't feel close to any particular party."),
                      (df['pronoun_nom'] + " doesn't know if " + df['pronoun_nom'] + " feels close to any particular party.")]
  df['party'] = np.select(party_condlist, party_choicelist, default="")

  # voting intention
  vote_condlist = [df['Q96']  == "Would not vote",
                   df['Q96'] == "Don't know",
                   df['Q96'] == "Refused to answer",
                   df['Q96'] != "Refused to answer"]
  vote_choicelist = [(df['pronoun_nom'] + " would not vote if a presidential election is held tomorrow."),
                     (df['pronoun_nom'] + " doesn't know who " + df['pronoun_nom'] + " would vote for if a presidential election is held tomorrow."),
                     "",
                     ("The political party of " + df['pronoun_pos'] + " preferred presidential candidate is " + df['Q96'] + ".")]
  df['vote'] = np.select(vote_condlist, vote_choicelist, default="")

  # create base prompt for each row
  df['demo_base'] = ("Consider the following person: A Ghanaian who lives in a " + df['URBRUR'] +
                     " area in the " + df['REGION'] +
                     " region of Ghana. " + df['pronoun_nom'] + " is " + df['Q1'].astype(int).astype(str) +
                     " years old. " + df['pronoun_nom'] + " is a " + df['Q100'] +
                     " and " + df['pronoun_pos'] + " race is " + df['Q101'] +
                     ". The primary language " + df['pronoun_nom'] + " speaks at home is " + df['Q2'] +
                     ". " + df['pronoun_pos'] + " highest level of education is " + df['Q94'] +
                     ". " + df['pronoun_pos'] + " religion is " + df['Q95'] +
                     ". " + df['pronoun_nom'] + " identifies as " + df['Q84A'] + ". " +
                     df['empl'] +
                     " " + df['pronoun_pos'] + " last occupation is " + df['Q93B'] +
                     ". " + df['pronoun_pos'] + " household's main source of water is " + df['Q91A'] +
                     ". " + df['elec'] +
                     " " + df['mobile'] +
                     " " + df['clinic'] +
                     " " + df['pronoun_nom'] + " feels " + df['Q4B'] +
                     " about " + df['pronoun_pos'] + " present living condition. " + df['party'] +
                     " " + df['vote'] +
                     " How do you think " + df['pronoun_nom'] + " would answer the question")

  # reconstruct priority variable
  conditions = [df['Q45PT1'].isin(['Health', 'AIDS', 'COVID-19', 'Sickness / Disease']),
                df['Q45PT1'].isin(['Nothing/ no problems', 'Refused', "Don't know"]),
                ~df['Q45PT1'].isin(['Nothing/ no problems', 'Refused', "Don't know"])]
  choices = ["Health-related issues such as health, sickness/disease, COVID-19 and AIDS",
             df['Q45PT1'],
             "Issues other than health such as the economy, food/agriculture, infrastructure, public services, country's governance and climate"]
  df['Q45PT1'] = np.select(conditions, choices, default=df['Q45PT1'])

  return df

# selected variables for Ghana round 9 Afrobarometer survey
columns_demo = "RESPNO, URBRUR, REGION, Q1, Q100, Q101, Q2, Q94, Q95, Q84A, Q93A, Q93B, EA_SVC_A, EA_SVC_B, EA_SVC_C, EA_SVC_D, EA_FAC_D, Q91A, Q92A, Q90F, Q90G, Q4B, Q89A, Q89B, Q96, Q4A, Q8"
columns_resp = "Q6C, Q41A, Q41B, Q41C, Q41D, Q41G, Q45PT1, Q57A, Q57B, Q58A, Q58B, Q58C, Q59, Q7A, Q7B, Q9A, Q9B, Q9C, Q11B, Q11C, Q11D, Q11E, Q31, Q33D, Q33E, Q33I, Q83C_GHA, Q86A, Q86B, Q86C, Q86D, Q86E, Q86F, Q90I"
question_text = ["Over the past year, how often, if ever, have you or anyone in your family gone without medicines or medical treatment?",
                 "In the past 12 months, have you had contact with a public clinic or hospital?",
                 "How easy or difficult was it to obtain the medical care or services you needed?",
                 "How often, if ever, did you have to pay a bribe, give a gift, or do a favor for a health worker or clinic or hospital staff in order to get the medical care or services you needed?",
                 "In general, when dealing with health workers and clinic or hospital staff, how much do you feel you can trust them?",
                 "How well or badly would you say the current government is improving basic health services, or haven't you heard enough to say?",
                 "In your opinion, what are the most important problems facing this country that government should address?",
                 "Please tell me whether you personally or any other member of your household have been affected by the COVID-19 pandemic by becoming ill with, or testing positive for, COVID-19?",
                 "Please tell me whether you personally or any other member of your household have been affected by the COVID-19 pandemic by temporarily or permanently losing a job, business, or primary source of income?",
                 "Have you received a vaccination against COVID-19, either one or two doses?",
                 "If a vaccine for COVID-19 is available , how likely are you to try to get vaccinated?",
                 "What is the main reason that you would be unlikely to get a COVID-19 vaccine?",
                 "How much do you trust the government to ensure that any vaccine for COVID-19 that is developed or offered to Ghanian citizens is safe before it is used in this country?",

                 "Over the past year, how often, if ever, have you or anyone in your family felt unsafe walking in your neighbourhood?",
                 "Over the past year, how often, if ever, have you or anyone in your family feared crime in your own home?",
                 "In this country, how free are you to say what you think?",
                 "In this country, how free are you to join any political organization you want?",
                 "In this country, how free are you to choose who to vote for without feeling pressured?",
                 "During the past year, how often have you contacted any local government councillor about some important problem or to give them your views?",
                 "During the past year, how often have you contacted any member of national assembly about some important problem or to give them your views?",
                 "During the past year, how often have you contacted any political party official about some important problem or to give them your views?",
                 "During the past year, how often have you contacted any traditional leader about some important problem or to give them your views?",
                 "Overall, how satisfied are you with the way democracy works in Ghana?",
                 "In your opinion, how often, in this country do people have to be careful of what they say about politics?",
                 "In your opinion, how often, in this country are people treated unequally under the law?",
                 "How often, if ever, are people treated unfairly by the government based on their economic status, that is, how rich or poor they are?",
                 "To whom do you normally go to first for assistance, when you are concerned about your security and the security of your family?",
                 "How much do you trust other Ghanaians?",
                 "How much do you trust your relatives?",
                 "How much do you trust your neighbours?",
                 "How much do you trust other people you know?",
                 "How much do you trust people from othe religions?",
                 "How much do you trust people from other ethnic groups?",
                 "How often do you use the Internet?"]

def synthetic_interview(df: pd.DataFrame) -> pd.DataFrame:
  """
  Create a survey dataset for synthetic interview approach;
  Included questions are: Q1, Q100, Q101, Q94, Q8, Q4A, Q9A, Q6C, Q41A, Q41B, Q41C, Q41D from Ghana round 9 of the Afrobarometer survey

  Parameters:
    df (pd.DataFrame): The cleaned survey data returned from the kitchen_sink_prompt function
  
  Returns:
    pd.DataFrame: The final survey data for LLM application in synthetic interview approach
  """

  # subset the data so that it only include subjects/interviewees with full response from selected questions
  df = df[df['Question'].isin(["Q6C", "Q41A", "Q41D", "Q9A"])]
  respondent_counts = df.groupby('ID_')['Question'].nunique()
  complete_respondents = respondent_counts[respondent_counts == df['Question'].nunique()].index
  df = df[df['ID_'].isin(complete_respondents)]

  # recategorise some variables
  edu_condlist = [df["Q94"].isin(["No formal schooling", "Informal schooling only (including Koranic schooling)"]),
                  df["Q94"].isin(["Some primary schooling", "Primary school completed"]),
                  df["Q94"].isin(["Intermediate school or Some secondary school / high school", "Secondary school / high school completed"]),
                  df["Q94"] == "Post-secondary qualifications, other than university e.g. a diploma or degree from a polytechnic or college",
                  ~df["Q94"].isin(["Don't know", "Refused"])]
  edu_recode = ["No formal schooling", "Primary school", "Secondary", "Diploma", "University"]
  df["education"] = np.select(edu_condlist, edu_recode, default = np.nan)

  race_condlist = [df["Q101"] == "Black / African",
                   df["Q101"] == "Coloured / Mixed race"]
  race_recode = ["Black", "Coloured"]
  df["race"] = np.select(race_condlist, race_recode, default = np.nan)

  # reorganise data
  unique_ids = df['ID_'].unique()
  new_prompt_file = []

  for check_now in unique_ids:
    # Filter data for the current ID
    val_set = df[df['ID_'] == check_now]

    # Extract unique answers - assuming one answer per ID per question
    answer_age = val_set['Q1'].unique()[0].astype(int).astype(str) #Q1
    answer_gender = val_set['Q100'].unique()[0] #Q100
    answer_race = val_set['race'].unique()[0] #Q101
    answer_education = val_set['education'].unique()[0] #Q94
    answer_political_conv = val_set['Q8'].unique()[0] #Q8
    answer_econ_assess = val_set['Q4A'].unique()[0] #Q4A
    answer_freedom = val_set[val_set['Question'] == 'Q9A']['Response'].iloc[0] #Q9A
    answer_medicine = val_set[val_set['Question'] == 'Q6C']['Response'].iloc[0] #Q6C
    answer_clinic = val_set[val_set['Question'] == 'Q41A']['Response'].iloc[0] #Q41A
    answer_health_trust = val_set[val_set['Question'] == 'Q41D']['Response'].iloc[0] #Q41D

    # Build text prompts
    QA_age = f"Interviewer: What is your age in years?\nMe: {answer_age}."
    QA_gender = f"Interviewer: What is your gender? Please respond with: Man or Woman.\nMe: {answer_gender}."
    QA_race = f"Interviewer: What is your race? Please respond with: Black or Coloured.\nMe: {answer_race}."
    QA_education = f"Interviewer: What is your highest level of education? Please respond with: university, diploma, secondary, primary school or no formal schooling.\nMe: {answer_education}."
    QA_political_conv = f"Interviewer: When you get together with your friends or family, how often would you say you discuss political matters? Please respond with: Occasionally, Never or Frequently.\nMe: {answer_political_conv}."
    QA_econ_assess = f"Interviewer: In general, how would you describe: The present economic condition of this country? Please respond with: Very good, Fairly good, Neither good nor bad, Fairly bad or Very bad.\nMe: {answer_econ_assess}."
    QA_freedom = f"Interviewer: In this country, how free are you: to say what you think? Please respond with: Completely free, Somewhat free, Not very free or Not at all free.\nMe: {answer_freedom}."
    QA_medicine = f"Interviewer: Over the past year, how often, if ever, have you or anyone in your family gone without: Medicines or medical treatment? Please respond with: Always, Many times, Several times, Just once or twice or Never.\nMe: {answer_medicine}."
    QA_clinic = f"Interviewer: In the past 12 months, have you had contact with a public clinic or hospital? Please respond with: Yes or No.\nMe: {answer_clinic}."
    QA_health_trust = f"Interviewer: In general, when dealing with health workers and clinic or hospital staff, how much do you feel you can trust them? Please respond with: A lot, A little bit, Somewhat, No contact or Not at all.\nMe: {answer_health_trust}."

    text_health_trust = f"{QA_age}\n{QA_gender}\n{QA_race}\n{QA_education}\n{QA_political_conv}\n{QA_econ_assess}\n{QA_freedom}\n{QA_medicine}\n{QA_clinic}\n{question_health_trust}"
    text_clinic = f"{QA_age}\n{QA_gender}\n{QA_race}\n{QA_education}\n{QA_political_conv}\n{QA_econ_assess}\n{QA_freedom}\n{QA_medicine}\n{QA_health_trust}\n{question_clinic}"
    text_medicine = f"{QA_age}\n{QA_gender}\n{QA_race}\n{QA_education}\n{QA_political_conv}\n{QA_econ_assess}\n{QA_freedom}\n{QA_clinic}\n{QA_health_trust}\n{question_medicine}"
    text_freedom = f"{QA_age}\n{QA_gender}\n{QA_race}\n{QA_education}\n{QA_political_conv}\n{QA_econ_assess}\n{QA_medicine}\n{QA_clinic}\n{QA_health_trust}\n{question_freedom}"
    text_econ_assess = f"{QA_age}\n{QA_gender}\n{QA_race}\n{QA_education}\n{QA_political_conv}\n{QA_freedom}\n{QA_medicine}\n{QA_clinic}\n{QA_health_trust}\n{question_econ_assess}"
    text_political_conv = f"{QA_age}\n{QA_gender}\n{QA_race}\n{QA_education}\n{QA_econ_assess}\n{QA_freedom}\n{QA_medicine}\n{QA_clinic}\n{QA_health_trust}\n{question_political_conv}"
    text_education = f"{QA_age}\n{QA_gender}\n{QA_race}\n{QA_political_conv}\n{QA_econ_assess}\n{QA_freedom}\n{QA_medicine}\n{QA_clinic}\n{QA_health_trust}\n{question_education}"
    text_race = f"{QA_age}\n{QA_gender}\n{QA_education}\n{QA_political_conv}\n{QA_econ_assess}\n{QA_freedom}\n{QA_medicine}\n{QA_clinic}\n{QA_health_trust}\n{question_race}"
    text_gender = f"{QA_age}\n{QA_race}\n{QA_education}\n{QA_political_conv}\n{QA_econ_assess}\n{QA_freedom}\n{QA_medicine}\n{QA_clinic}\n{QA_health_trust}\n{question_gender}"
    text_age = f"{QA_gender}\n{QA_race}\n{QA_education}\n{QA_political_conv}\n{QA_econ_assess}\n{QA_freedom}\n{QA_medicine}\n{QA_clinic}\n{QA_health_trust}\n{question_age}"

    # Append the result to the list
    new_prompt_file.append({
        'ID': check_now,
        'text_health_trust': text_health_trust,
        'text_clinic': text_clinic,
        'text_medicine': text_medicine,
        'text_freedom': text_freedom,
        'text_econ_assess': text_econ_assess,
        'text_political_conv': text_political_conv,
        'text_education': text_education,
        'text_race': text_race,
        'text_gender': text_gender,
        'text_age': text_age,
        'answer_health_trust': answer_health_trust,
        'answer_clinic': answer_clinic,
        'answer_medicine': answer_medicine,
        'answer_freedom': answer_freedom,
        'answer_econ_assess': answer_econ_assess,
        'answer_political_conv': answer_political_conv,
        'answer_education': answer_education,
        'answer_race': answer_race,
        'answer_gender': answer_gender,
        'answer_age': answer_age

    })

  # Convert the list to a DataFrame for easier manipulation or export
  new_prompt_df = pd.DataFrame(new_prompt_file)

  return new_prompt_df