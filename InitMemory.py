import requests
import os 
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime 
import json

load_dotenv()

ticker = "meta" #tsla, msft, nvda, meta

ticker_to_company = {
    "tsla": "Tesla",
    "msft": "Microsoft",
    "nvda": "Nvidia",
    "meta": "Meta",
}
stock = ticker_to_company.get(ticker.lower(), "Unknown")


hisFolder = 'HistoricalData'
earFolder = 'EarningsData'
esgFolder = 'ESGScores'
finFolder = 'Financial Analytics Metrics'
treFolder = 'Trend Indicator Scores'
keyFolder = 'Key Statistics'
newsFolder = 'News'

todaysDate = datetime.now().strftime('%d-%m-%Y')

historicalURL = f"https://yahoo-finance127.p.rapidapi.com/historic/{ticker}/1d/3mo"
earningsURL = f"https://yahoo-finance127.p.rapidapi.com/earnings/{ticker}"
ESGURL = f"https://yahoo-finance127.p.rapidapi.com/esg-score/{ticker}"
finAnalyticsURL = f"https://yahoo-finance127.p.rapidapi.com/finance-analytics/{ticker}"
trendURL = f"https://yahoo-finance127.p.rapidapi.com/earnings-trend/{ticker}"
keyStatisticsURL = f"https://yahoo-finance127.p.rapidapi.com/key-statistics/{ticker}"
newsURL = f"https://reuters-business-and-financial-news.p.rapidapi.com/get-articles-by-keyword-name/{stock}/0/15"

yahooHeaders = {
    "X-RapidAPI-Key": os.getenv('RAPIDAPI_KEY'),
    "X-RapidAPI-Host": os.getenv('YAHOO_RAPIDAPI_HOST')
}

reuterHeaders = {
    "X-RapidAPI-Key": os.getenv('RAPIDAPI_KEY'),
    "X-RapidAPI-Host": os.getenv('REUTERS_RAPIDAPI_HOST')
}

hisRes = requests.get(historicalURL, headers=yahooHeaders)
earRes = requests.get(earningsURL, headers=yahooHeaders)
esgRes = requests.get(ESGURL , headers=yahooHeaders)
finRes = requests.get(finAnalyticsURL, headers=yahooHeaders)
treRes = requests.get(trendURL, headers=yahooHeaders)
keyRes = requests.get(keyStatisticsURL, headers=yahooHeaders)
newsRes = requests.get(newsURL, headers=reuterHeaders)

# HISTORICAL PRICE DATA

#filter out the info
hisJSON = hisRes.json()
hisTimestamps = hisJSON['timestamp']
hisOpens = hisJSON['indicators']['quote'][0]['open']
hisCloses = hisJSON['indicators']['quote'][0]['close'] 
hisVolumes = hisJSON['indicators']['quote'][0]['volume']

#dataframe
hisdf = pd.DataFrame({
    'Timestamp': hisTimestamps,
    'Open': hisOpens,
    'Close': hisCloses,
    'Volume': hisVolumes
})

#clean up date 
hisdf['Date'] = pd.to_datetime(hisdf['Timestamp'], unit='s').dt.strftime('%d-%m-%Y')
hisdf.drop('Timestamp', axis=1, inplace=True)

#create folder if doesnt exist
if not os.path.exists(hisFolder):
    os.makedirs(hisFolder)

#deletes any previous files in the folder with the given ticker
for filename in os.listdir(hisFolder):
    if filename.startswith(ticker):
        os.remove(os.path.join(hisFolder, filename))

#save the dataframe to folder
hisFilepath = os.path.join(hisFolder, f'{ticker}_Historical.csv')
hisdf.to_csv(hisFilepath, index=False)

#EARNINGS

earJSON = earRes.json()

def extract_financials_data(financials_data):
    # Initialize a list to store extracted data
    extracted_data = []

    # Process yearly data
    for item in financials_data['yearly']:
        extracted_data.append({
            'Date': item['date'],
            'Type': 'Yearly',
            'Revenue': item['revenue']['fmt'],
            'Earnings': item['earnings']['fmt']
        })

    # Process quarterly data
    for item in financials_data['quarterly']:
        extracted_data.append({
            'Date': item['date'],
            'Type': 'Quarterly',
            'Revenue': item['revenue']['fmt'],
            'Earnings': item['earnings']['fmt']
        })

    return pd.DataFrame(extracted_data)

eardf = extract_financials_data(earJSON['financialsChart'])

#create folder if doesnt exist
if not os.path.exists(earFolder):
    os.makedirs(earFolder)

#deletes any previous files in the folder with the given ticker
for filename in os.listdir(earFolder):
    if filename.startswith(ticker):
        os.remove(os.path.join(earFolder, filename))

#save the dataframe to folder
earFilepath = os.path.join(earFolder, f'{ticker}_Earnings.csv')
eardf.to_csv(earFilepath, index=False)

#ESG

esgJSON = esgRes.json()
ESGdata = {
    'Total ESG Score': esgJSON['totalEsg']['fmt'],
    'Environment Score': esgJSON['environmentScore']['fmt'],
    'Social Score': esgJSON['socialScore']['fmt'],
    'Governance Score': esgJSON['governanceScore']['fmt'],
    'Rating Year': esgJSON['ratingYear'],
}

esgdf = pd.DataFrame([ESGdata])

#create folder if doesnt exist
if not os.path.exists(esgFolder):
    os.makedirs(esgFolder)

#deletes any previous files in the folder with the given ticker
for filename in os.listdir(esgFolder):
    if filename.startswith(ticker):
        os.remove(os.path.join(esgFolder, filename))

#save the dataframe to folder
esgFilepath = os.path.join(esgFolder, f'{ticker}_ESGscore.csv')
esgdf.to_csv(esgFilepath, index=False)

#FINANCIAL ANALYTICS 
finJSON = finRes.json()
finData = {key: value['fmt'] if isinstance(value, dict) and 'fmt' in value else value 
                  for key, value in finJSON.items()}

findf = pd.DataFrame([finData])

findf.drop('maxAge', axis=1, inplace=True)
findf.drop('numberOfAnalystOpinions', axis=1, inplace=True)
findf.drop('grossProfits', axis=1, inplace=True)
findf.drop('financialCurrency', axis=1, inplace=True)
findf.drop('recommendationKey', axis=1, inplace=True)
findf.drop('recommendationMean', axis=1, inplace=True)

#create folder if doesnt exist
if not os.path.exists(finFolder):
    os.makedirs(finFolder)

#deletes any previous files in the folder with the given ticker
for filename in os.listdir(finFolder):
    if filename.startswith(ticker):
        os.remove(os.path.join(finFolder, filename))

#save the dataframe to folder
finFilepath = os.path.join(finFolder, f'{ticker}_Financials.csv')
findf.to_csv(finFilepath, index=False)

#TRENDS 
treJSON = treRes.json()

def extract_fmt_values(data):
    extracted_data = {}
    for key, value in data.items():
        if isinstance(value, dict):  # Check if the value is a dictionary
            if 'fmt' in value:  # Check if 'fmt' is a key in this dictionary
                extracted_data[key] = value['fmt']  # Extract 'fmt' value
            else:
                # Recursive call to handle nested dictionaries
                nested_data = extract_fmt_values(value)
                for nested_key, nested_value in nested_data.items():
                    # Construct new key to avoid overwriting in case of duplicate keys in nested dictionaries
                    new_key = f"{key}_{nested_key}"
                    extracted_data[new_key] = nested_value
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            # Handle list of dictionaries (assuming structure consistency)
            for i, item in enumerate(value):
                nested_data = extract_fmt_values(item)
                for nested_key, nested_value in nested_data.items():
                    new_key = f"{key}_{i}_{nested_key}"
                    extracted_data[new_key] = nested_value
    return extracted_data

# Extracting "fmt" values
treData = extract_fmt_values(treJSON)

# Converting to DataFrame for easy viewing/manipulation
tredf = pd.DataFrame([treData])

tredf.drop('epsRevisions_downLast30days', axis=1, inplace=True)
tredf.drop('epsRevisions_upLast30days', axis=1, inplace=True)
tredf.drop('epsRevisions_upLast7days', axis=1, inplace=True)
tredf.drop('earningsEstimate_numberOfAnalysts', axis=1, inplace=True)
tredf.drop('revenueEstimate_numberOfAnalysts', axis=1, inplace=True)

#create folder if doesnt exist
if not os.path.exists(treFolder):
    os.makedirs(treFolder)

#deletes any previous files in the folder with the given ticker
for filename in os.listdir(treFolder):
    if filename.startswith(ticker):
        os.remove(os.path.join(treFolder, filename))

#save the dataframe to folder
treFilepath = os.path.join(treFolder, f'{ticker}_TrendScores.csv')
tredf.to_csv(treFilepath, index=False)

#KEY STATISTICS

keyJSON = keyRes.json()

# Extracting "fmt" values
keyData = extract_fmt_values(keyJSON)

# Converting to DataFrame for easy viewing/manipulation
keydf = pd.DataFrame([keyData])
keydf.drop('askSize', axis=1, inplace=True)

#create folder if doesnt exist
if not os.path.exists(keyFolder):
    os.makedirs(keyFolder)

#deletes any previous files in the folder with the given ticker
for filename in os.listdir(keyFolder):
    if filename.startswith(ticker):
        os.remove(os.path.join(keyFolder, filename))

#save the dataframe to folder
keyFilepath = os.path.join(keyFolder, f'{ticker}_KeyStatistics.csv')
keydf.to_csv(keyFilepath, index=False)

#NEWS DATA 

newsJSON = newsRes.json()

# Define a list to store extracted information for each article
newsData = []

# Iterate through each article in the newsJSON
for article in newsJSON['articles']:
    # Extract the needed information
    title = article['articlesName']
    short_description = article['articlesShortDescription']
    
    # Parse the 'articlesDescription' string into a Python list of dictionaries
    articles_description = json.loads(article['articlesDescription'])
    
   
    # Extract and format the publishing date
    publishing_date = datetime.strptime(article['dateModified']['date'], '%Y-%m-%d %H:%M:%S.%f').strftime('%d-%m-%Y')
    
    # Append the information to the list
    newsData.append({
        'Title': title,
        'Short Description': short_description,
        'Publishing Date': publishing_date
    })

# Convert the list of dictionaries to a DataFrame
newsdf = pd.DataFrame(newsData)

#create folder if doesnt exist
if not os.path.exists(newsFolder):
    os.makedirs(newsFolder)

#deletes any previous files in the folder with the given ticker
for filename in os.listdir(newsFolder):
    if filename.startswith(ticker):
        os.remove(os.path.join(newsFolder, filename))

#save the dataframe to folder
newsFilepath = os.path.join(newsFolder, f'{ticker}_News.csv')
newsdf.to_csv(newsFilepath, index=False)


