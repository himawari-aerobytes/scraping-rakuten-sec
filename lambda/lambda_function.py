import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import datetime
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
import requests
import json
import matplotlib.pyplot as plt
import pandas as pd
from io import StringIO
import japanize_matplotlib


# 現在時刻の取得
def getNowTimeString():
    # 時間の設定
    t_delta = datetime.timedelta(hours=9)
    JST = datetime.timezone(t_delta, 'JST')
    now = datetime.datetime.now(JST)
    return now.strftime("%Y%m%d%H%M%S")

def getNowTimeStringYYYYmmddHHMMSS():
    # 時間の設定
    t_delta = datetime.timedelta(hours=9)
    JST = datetime.timezone(t_delta, 'JST')
    now = datetime.datetime.now(JST)
    return now.strftime("%Y-%m-%d %H:%M:%S")

def upload_to_s3(local_path, bucket_name, object_key):
    s3_client = boto3.client('s3')
    s3_client.upload_file(local_path, bucket_name, object_key)
    return f"https://{bucket_name}.s3.amazonaws.com/{object_key}"


# グラフのプロット
def plotGraph(new_df, local_graph_path):
    plt.figure(figsize=(10, 6))
    plt.plot(new_df.index, new_df['国内株式'], label='国内株式',marker='o')
    plt.plot(new_df.index, new_df['米国株式'], label='米国株式',marker='o')
    # plt.plot(new_df.index, new_df['債権'], label='債権')
    plt.plot(new_df.index, new_df['投資信託'], label='投資信託',marker='o')

    plt.xlabel('Date')
    plt.ylabel('Value')
    plt.title('Investment Values Over Time')
    plt.legend()
    plt.grid(True)

    # プロットを保存
    plt.savefig(local_graph_path, format='png')

    return local_graph_path

def generate_presigned_url(bucket_name, object_key, expiration=3600):
    s3_client = boto3.client('s3')
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': object_key},
                                                    ExpiresIn=expiration)
    except (NoCredentialsError, PartialCredentialsError) as e:
        print("Credentials not available: ", e)
        return None
    return response

def getPortfolioData(portfolio_table_data,pl,capitalization):
    for data in portfolio_table_data:
        title = data.find_element(By.TAG_NAME,'th').text
        values = data.find_elements(By.TAG_NAME, 'td')
        count = 0
        for value in values:
            value = value.text.replace('円','')
            # 中国株式,ASEAN株式のスキップ
            if value == '':
                continue
            if count == 1:
                pl[title]=value.replace('+','').replace('\n', '')
               
            else:
                capitalization[title]=int(value.replace('\n', '').replace(',',''))
                
            count+=1

# S3から既存のCSVを取得して追記、存在しない場合は新規作成
def getS3ExistingData(new_df,bucket_name, csv_key):
    combined_df = None
    s3_client = boto3.client('s3')
    try:
        s3_object = s3_client.get_object(Bucket=bucket_name, Key=csv_key)
        existing_df = pd.read_csv(s3_object['Body'])
        existing_df['date'] = pd.to_datetime(existing_df['date'], format='%Y-%m-%d %H:%M:%S')
        combined_df = pd.concat([existing_df, new_df])
    except s3_client.exceptions.NoSuchKey:
        combined_df = new_df
    return combined_df

# pandasDataFrameをS3にアップロード
def uploadDfToS3(df, bucket_name, object_key):
    df.reset_index(inplace= True)
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    s3_resource = boto3.resource('s3')
    s3_resource.Object(bucket_name, object_key).put(Body=csv_buffer.getvalue())


def send_LINE(local_path,bucket_name,object_key):
    line_channel_access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("USER_ID")

    # 画像をS3にアップロードしてURLを取得
    upload_to_s3(local_path, bucket_name, object_key)
    # 署名付きURLの有効期限
    expiration = 60*60*24*14
    uploaded_image_url = generate_presigned_url(bucket_name, object_key,expiration)
    headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {line_channel_access_token}"
    }
        
    data = {
        "to": user_id,
        "messages": [
            {
                "type": "image",
                "originalContentUrl": uploaded_image_url,
                "previewImageUrl": uploaded_image_url
            }
        ]
    }
        
    response = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers=headers,
        data=json.dumps(data)
    )
        
    return {
        'statusCode': response.status_code,
        'body': response.text
    }

def lambda_handler(event,context):

    load_dotenv()

    # Optionの設定
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--single-process")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280x1696")
    chrome_options.add_argument("--user-data-dir=/tmp/user-data")
    chrome_options.add_argument("--data-path=/tmp/data-path")
    chrome_options.add_argument("--disk-cache-dir=/tmp/cache-dir")
    chrome_options.add_argument("--homedir=/tmp")
    chrome_options.binary_location = "/opt/chrome/chrome"

    driver = webdriver.Chrome(options=chrome_options, service=Service("/opt/chromedriver"))

    driver.get('https://www.rakuten-sec.co.jp/ITS/V_ACT_Login.html') #特定のURLへ移動
    time.sleep(1)

    # ログイン処理
    loginId = driver.find_element(By.NAME, 'loginid')
    password = driver.find_element(By.NAME, 'passwd')

    loginId.clear()
    password.clear()

    loginId.send_keys(os.environ.get("ID"))
    password.send_keys(os.environ.get("PASS"))

    loginId.submit()

    time.sleep(5)
    allBreakdown=driver.find_element(By.ID,'homeAssetsTrigger')
    allBreakdown.click()
    time.sleep(5)
    portfolio = driver.find_element(By.ID, 'balance_data_actual_data')

    # ポートフォリオデータ取得
    portfolio_table_data = portfolio.find_element(By.TAG_NAME,'tbody').find_elements(By.TAG_NAME,'tr')
    pl = {}
    capitalization = {}

    getPortfolioData(portfolio_table_data, pl, capitalization)

    # 新しいデータをデータフレームとして追加
    capitalization["date"]=getNowTimeStringYYYYmmddHHMMSS()# 日付を��加
    bucket_name = os.environ.get("BUCKET_NAME")
    new_df = getS3ExistingData(pd.DataFrame([capitalization]), bucket_name, 'portfolio.csv')

    # 結合したデータをCSV形式に変換
    csv_buffer = StringIO()
    new_df.to_csv(csv_buffer, index=False)

    # 日付をインデックスとして設定
    new_df['date'] = pd.to_datetime(new_df['date'], format='%Y-%m-%d %H:%M:%S')
    new_df.set_index('date', inplace=True)

    # プロット
    now = getNowTimeString()
    local_graph_path = '/tmp/'+now+'_graph.png'
    plotGraph(new_df, local_graph_path)
    uploadDfToS3(new_df, os.environ.get("BUCKET_NAME"), 'portfolio.csv')

    # S3オブジェクト名セット
    bucket_folder = os.environ.get("BUCKET_FOLDER")
    graph_object_key = now+'_graph.png'
    table_object_key = now+'_screenshot.png'
    if(bucket_folder):
        print("bucket folderに入りました")
        graph_object_key = f"{bucket_folder}/{graph_object_key}"
        table_object_key = f"{bucket_folder}/{table_object_key}"
    
    #upload_to_s3(local_graph_path, os.environ.get("BUCKET_NAME"), graph_object_key)

    # 画面最大化
    driver.maximize_window()

    time.sleep(5)

    local_path= '/tmp/'+now+'_screenshot.png'
    portfolio.screenshot(local_path)
    driver.quit()
    
    # LINE送信処理
    send_LINE(local_path,bucket_name,table_object_key)
    return send_LINE(local_graph_path,bucket_name,graph_object_key)


