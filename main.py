from selenium import webdriver
from tempfile import mkdtemp
from selenium.webdriver.common.by import By
from selenium.common.exceptions import ElementNotInteractableException, ElementClickInterceptedException, \
    NoSuchElementException
import time
import boto3
import datetime


def handler(event, context):
    orig = event['origin']
    dest = event['destination']
    data = event['date']
    month = event['month']
    year = event['year']
    hour = event['hour']
    options = webdriver.ChromeOptions()
    service = webdriver.ChromeService("/opt/chromedriver")
    options.binary_location = '/opt/chrome/chrome'
    options.add_argument("--headless=new")
    options.add_argument('--no-sandbox')
    options.add_argument("--disable-gpu")
    options.add_argument("--single-process")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-dev-tools")
    options.add_argument("--no-zygote")
    options.add_argument(f"--user-data-dir={mkdtemp()}")
    options.add_argument(f"--data-path={mkdtemp()}")
    options.add_argument(f"--disk-cache-dir={mkdtemp()}")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("window-size=1920,1080")
    options.add_argument('--blink-settings=imagesEnabled=false')

    def route(origin, destination, day_check, month_check, year_check, hour_check):
        driver = webdriver.Chrome(service=service, options=options)
        url = 'https://www.renfe.com/es/en'
        driver.get(url)
        while True:
            try:
                cookie = driver.find_element(By.CSS_SELECTOR, "button[id='onetrust-accept-btn-handler']")
                cookie.click()
                break
            except NoSuchElementException:
                time.sleep(2)
            except ElementClickInterceptedException:
                pass

        origin_station = driver.find_element(By.CSS_SELECTOR, "input#origin")
        origin_station.send_keys(origin)
        driver.find_elements(By.CSS_SELECTOR, "li[role='option']")[0].click()
        time.sleep(1)

        destination_station = driver.find_element(By.CSS_SELECTOR, "input#destination")
        destination_station.send_keys(destination)

        try:
            driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div[1]/div/div/div/div/div/div/rf-header"
                                          "/rf-header-top/div/div[2]/rf-search/div/div[1]/rf-awesomplete[2]/div/"
                                          "div[1]/ul/li[1]").click()
        except ElementNotInteractableException:
            time.sleep(2)

        trip_type = driver.find_element(By.CLASS_NAME, 'rf-select__text')
        trip_type.click()
        time.sleep(1)
        one_way = driver.find_element(By.CLASS_NAME, 'rf-select__list-text')
        one_way.click()
        time.sleep(1)

        driver.find_element(By.CLASS_NAME, 'rf-daterange__ipt').click()
        time.sleep(1)

        months_to_check = []
        init_months = driver.find_elements(By.CSS_SELECTOR, "span[class='rf-daterange__month-label']")
        for init_month in init_months:
            month_to_check = init_month.find_elements(By.CSS_SELECTOR, 'span')
            for x in month_to_check:
                x = x.text
                months_to_check.append(x)

        month_char = datetime.date(1900, int(month_check), 1).strftime('%B') + year_check
        while month_char not in months_to_check:
            driver.find_element(By.CLASS_NAME, 'lightpick__next-action').click()
            time.sleep(1)
            months_to_check = []
            init_months = driver.find_elements(By.CSS_SELECTOR, "span[class='rf-daterange__month-label']")
            for init_month in init_months:
                month_to_check = init_month.find_elements(By.CSS_SELECTOR, 'span')
                for x in month_to_check:
                    x = x.text
                    months_to_check.append(x)

        which_month = driver.find_elements(By.CLASS_NAME, 'lightpick__month')
        if int(month_check) % 2 == 1:
            chosen_month = which_month[0]
        else:
            chosen_month = which_month[1]
        days = chosen_month.find_elements(By.CLASS_NAME, 'lightpick__day')
        for x in days:
            if int(x.text) == day_check:
                x.click()
                time.sleep(1)
                break
        time.sleep(1)

        accept_btn = driver.find_element(By.CSS_SELECTOR, "button[class='lightpick__apply-action-sub']")
        accept_btn.click()
        time.sleep(1)

        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()
        time.sleep(1)
        while True:
            try:
                driver.find_element(By.XPATH,
                                    f'/html/body/article/section/div/div[1]/div/div[3]/div[1]/'
                                    f'div[{1}]/div[1]/h5[1]')
                break
            except NoSuchElementException:
                time.sleep(15)
        time.sleep(10)
        price_send = ""
        for i in range(1, 50):
            try:
                hour_get = driver.find_element(By.XPATH,
                                               f'/html/body/article/section/div/div[1]/div/div[3]/div[1]/'
                                               f'div[{i}]/div[1]/h5[1]').text
            except NoSuchElementException:
                break
            if hour_check in hour_get:
                price_send = driver.find_element(By.XPATH,
                                                 f'/html/body/article/section/div/div[1]/div/div[3]/div[1]'
                                                 f'/div[{i}]/div[3]/span').text
        driver.close()
        driver.quit()
        return float(price_send.split("\n")[1].split(" ")[0].replace(",", ".")) * 2

    price = route(orig, dest, data, month, year, hour)
    client = boto3.client('s3', 'eu-north-1')
    bucket_name = 'data-store-lambda'
    s3_path = event['s3_path']

    read_from_s3 = client.get_object(
        Key=s3_path,
        Bucket=bucket_name
    )
    new_list = read_from_s3["Body"].read().decode("utf-8")
    new_list += f"{price},"
    client.put_object(
        Key=s3_path,
        Bucket=bucket_name,
        Body=new_list.encode("utf-8")
    )
    return {"Status Code": 200}
