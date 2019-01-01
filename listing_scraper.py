#!/usr/bin/env python3.6

# data cleaning, html parsing, and date/time management libraries
import numpy as np
import pandas as pd
import requests
import html5lib
import time
import datetime as dt
import pytz

# Selenium & BeautifulSoup scraping/web browser automation libraries
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait # available since 2.4.0
from selenium.webdriver.support import expected_conditions as EC # available since 2.26.0
from google.cloud import bigquery
from time import sleep
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--url",<#REPLACE ME>')
parser.add_argument("--selenium",default="http://selenium:4444/wd/hub")
client = bigquery.Client()
TODAY = str(dt.date.today())

# helper funcs

def get_soup(driver):
    """
    Creates a beautiful soup object (bs4.BeautifulSoup) from an active selenium driver instance
    for purposes of parsing the underlying HTML code.
    
    Parameters
    ----------
    driver : Selenium webdriver object. Must execute driver.get(url) prior to
             calling this get_soup() function
    """
    return BeautifulSoup(driver.page_source,'html5lib')

def gprint(text):
    """
    Colored print function. Prints text in green
    
    Parameters
    ----------
    text : string
    """
    print ("\x1b[32m{0}\x1b[0m".format(text))    

def bprint(text):
    """
    Colored print function. Prints text in blue
    
    Parameters
    ----------
    text : string
    """
    print ("\x1b[34m{0}\x1b[0m".format(text))
    
def get_printable_reports_url(driver):
    """
    Finds the custom url hidden behind the 'Printable Reports' link
    located at the top portion of the mls listings page. Returns string
    value of url.
    
    Parameters
    ----------
    driver : Selenium webdriver object. Must execute driver.get(url) prior to
             calling this function
    """
    return driver.find_element_by_link_text('Printable Reports').get_property('href')
                    
def open_printable_reports_page(driver):
    """
    Loads the printable reports page in a new tab. Webdriver switches window
    to newly opened tab. Either text link at the top 1/4 of page says "Printable Reports"
    or a small printer icon that re-directs the url with some js code is used to
    open the new tab
    
    Parameters
    ----------
    
    driver : Selenium webdriver object. Must execute driver.get(url) prior to
             calling this function
    """
    try:
        driver.find_element_by_link_text('Printable Reports').click()
    except:
        driver.find_elements_by_class_name("icon-print-report")[0].click()
        
    sleep(5)
    driver.switch_to.window(driver.window_handles[1]) #Points selenium driver to the new tab
    assert driver.title == "Customer Report"
    print("")
                    
def get_listing_entry(num,soup):
    """
    Finds the HTML location for each housing listing available.
    Returns beautifulsoup object
  
    Parameters
    ----------
    num : integer value corresponding to the listing number
          of a given housing property on the mls printable reports site
          values start from 0
          
    soup : beautifulsoup object from running the get_soup() function
           with a webdriver object after loading the printable reports page
    """
    return soup.findAll('span',{'id':'L{}'.format(num)})[0]

def get_listing_id(listing):
    """
    Finds the mls generated unique id for a particular housing listing
    
    Parameters
    ----------
    listing : beautifulsoup object that is returned after
              running the get_listing_entry() function
    """
    return listing.findAll('table')[1].find('div')['id']

def get_listing_photo_count(listing):
    """
    Count the number of images associated with an indivdual housing listing
    on the mls printable reports site.
    
    Parameters
    ----------
    listing : beautifulsoup object that is returned after
              running the get_listing_entry() function
    """
    return int(listing.findAll('div',
                           {'id':"CountDiv{id_}"\
                                .format(id_=get_listing_id(listing))
                            }
                          )[0].text.replace('\xa0HD','').split()[~0])
                          
def get_listing_total(soup):
    """
    Finds the total number of housing listings on the mls
    Printable reports page
    
    Parameters
    ----------
    soup : beautifulsoup object returned from runing
           the get_soup() function after loading the
           printable reports site in the selenium webdriver
    """
  
    listing_count = 0
    for i in range(100):
        if soup.findAll('span',{'id':f"L{i}"}) != []:
            listing_count += 1
    return listing_count

def get_results(listing,driver):
    """
    Single function that acquires all data corresiponding to an individual
    mls listing. Results are returned as a dictionary object
    
    Parameters
    ----------
    listing : beautifulsoup object that is returned after
              running the get_listing_entry() function
    """
    
    def get_thumbnail_urls(listing):
        """
        Finds and returns a list of all urls for all thumbnail images
        of a given housing listing on the mls printable reports page
        
        Parameters
        ----------
        listing : beautifulsoup object that is returned after
                  running the get_listing_entry() function
        """
        try:
            id_ = get_listing_id(listing)
            photo_count = get_listing_photo_count(listing)
            return [f'http://pxlimages.xmlsweb.com/NJMLS/M/Images/{id_}.{cnt}.JPG?v=1' for cnt in range(1, photo_count + 1)]
        except:
            return [listing.find('img')['src']]
                    
    def get_box_vals(listing):
        """
        Finds basic information about a given housing listing on mls. This is the block of
        information that adjacent to the right of the thumbnail image for each listing
        Including: last price, ml_num, address, town, zipcode, county, county locale,
                   area code, direct, original listing price, days on market
                   
        Parameters
        ----------
        listing : beautifulsoup object that is returned after
                  running the get_listing_entry() function
        """
        box = listing.findAll('td',{'width':'55%'})[0]
        last_price = int(box.text.strip().replace('\t','').split("LP:\n")[1].split('\n')[0].replace("$",'').replace(",",''))
        ml_num = box.text.strip().replace('\t','').split("ML#:\n")[1].split('\n')[0].strip()
        address = box.text.strip().replace('\t','').split("Addr:\n")[1].split('\n')[0].strip()
        town = box.text.strip().replace('\t','').split("Town:\n")[1].split('\n')[0].strip()
        zipcode = box.text.strip().replace('\t','').split("Zip:\n")[1].split('\n')[0].strip()
        county = box.text.strip().replace('\t','').split("County:\n")[1].split('\n')[0].title().strip()
        county_locale = box.text.strip().replace('\t','').split("County Locale#:\n")[1].split('\n')[0].strip()
        areacode = box.text.strip().replace('\t','').split("Area#:\n")[1].split('\n')[0].strip()
        direct = box.text.strip().replace('\t','').split("Direct:\n")[1].split('\n')[0].strip()
        original_lp = int(box.text.strip().replace('\t','').split("Orig LP:\n")[1].split('\n')[0].replace("$",'').replace(",",''))
        days_on_mkt = int(box.text.strip().replace('\t','').split("DOM:\n")[1].split('\n')[0])
        
        return {"last_price":last_price,
                "ml_num":ml_num,
                "address":address,
                "town":town,
                "zipcode":zipcode,
                "county":county,
                "county_locale":county_locale,
                "areacode":areacode,
                "direct":direct,
                "original_lp":original_lp,
                "days_on_mkt":days_on_mkt}

     """Account for 'Virtual Tour' link. Data for listings that include the 'Virtual Tour' are offset by 1 when compared
     To the listings that do not contain the 'Virtual Tour' link. The VT variable is boolean and coerced into an integer
     That way, adding VT to the row index accounts for row offset."""
    VT = True if 'Virtual'.lower() in listing.text.lower() and 'Tour'.lower() in listing.text.lower() else False
    if driver.current_url == "http://www.priv.njmlsnew.xmlsweb.com/reportsPDF.asp":
        VT = 0
                    
    results1 = dict(zip([x for x in listing.findAll('table')[15 + VT].text.replace('#\n\n','#').split('\n\t') if x != '\n'],
                        [x for x in listing.findAll('table')[16 + VT].text.replace('#\n\n','#').replace("\xa0",'empty').split('\n\t') if x != '\n']))
    try:
        results1['Tax Condo #'] = results1.get('Tax Condo #').replace('\n\n','')
    except:
        results1['Tax Condo #'] = 'empty'
    results2 = dict(zip([x for x in listing.findAll('table')[17 + VT].text.replace('Sub-Style\n\n','Sub-Style').split('\n\t') if x != '\n'],
                        [x for x in listing.findAll('table')[18 + VT].text.replace('#\n\n','#').replace("\xa0","empty").split('\n\t') if x != '\n']))
    try:
        results2['Sub-Style'] = results2.get('Sub-Style').replace('\n\n','')
    except:
        results2['Sub-Style'] = 'empty'
    try:
        results2['Taxes'] = results2.get('Taxes').replace("$","").replace(",","")
    except:
        results2['Taxes'] = 'empty'
    
    monthly_maintenance = listing.findAll('table')[19 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","")
    maintenance_includes = listing.findAll('table')[19 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty')
    gnd_flr = listing.findAll('table')[20 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty')
    EL = listing.findAll('table')[20 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty')
    first_fl = listing.findAll('table')[21 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty')
    JH = listing.findAll('table')[21 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty')
    second_fl = listing.findAll('table')[22 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty')
    SH = listing.findAll('table')[22 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty')
    third_fl = listing.findAll('table')[23 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty')
    basement = listing.findAll('table')[24 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty')
    assessments = listing.findAll('table')[25 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty')
    municipal_assessment = listing.findAll('table')[25 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty')
    try:
        # some reason, this value is not entered and the contents returns [] - so the try/catch is used
        easements = listing.findAll('table')[25 + VT].findAll('td')[5].contents[0].replace("$","").replace(",","").replace('\xa0','empty')
    except:
        easements = 'empty'
    items_included = listing.findAll('table')[26 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty')
    items_not_included = listing.findAll('table')[26 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty')
    
    results3 = {
        "monthly_maintenance":monthly_maintenance,
        "maintenance_includes":maintenance_includes,
        "gnd_flr":gnd_flr,
        "elementary_school":EL,
        "first_fl":first_fl,
        "jr_highschool":JH,
        "second_fl":second_fl,
        "high_school":SH,
        "third_fl":third_fl,
        "basement":basement,
        "assessments":assessments,
        "municipal_assessment":municipal_assessment,
        "easements":easements,
        "items_included":items_included,
        "items_not_included":items_not_included,
    }
    
    building_complex = listing.findAll('table')[28 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    unit_num = listing.findAll('table')[28 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    model_line = listing.findAll('table')[28 + VT].findAll('td')[5].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    approx_unit_sqtf = listing.findAll('table')[29 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    underlying_mtg = listing.findAll('table')[29 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    yrs_remaining = listing.findAll('table')[29 + VT].findAll('td')[5].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    number_of_shares = listing.findAll('table')[30 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip() 
    number_of_stories = listing.findAll('table')[30 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip() 
    stairs = listing.findAll('table')[30 + VT].findAll('td')[5].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    building_assoc_charges = listing.findAll('table')[31 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    board_finance_requirements = listing.findAll('table')[31 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    management_company = listing.findAll('table')[32 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    management_phone = listing.findAll('table')[32 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()

    results4 = {
        "building_complex":building_complex,
        "unit_num":unit_num,
        "model_line":model_line,
        "approx_unit_sqtf":approx_unit_sqtf,
        "underlying_mtg":underlying_mtg,
        "yrs_remaining":yrs_remaining,
        "number_of_shares":number_of_shares,
        "number_of_stories":number_of_stories,
        "stairs":stairs,
        "building_assoc_charges":building_assoc_charges,
        "board_finance_requirements":board_finance_requirements,
        "management_company":management_company,
        "management_phone":management_phone
    }

    waterfront = listing.findAll('table')[34 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    garage = listing.findAll('table')[34 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    life_style = listing.findAll('table')[35 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    heating = listing.findAll('table')[36 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    cooling = listing.findAll('table')[36 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    fireplace = listing.findAll('table')[37 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    basement_features = listing.findAll('table')[37 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    building_amenities = listing.findAll('table')[38 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    maintenance_included = listing.findAll('table')[38 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    appliances_included = listing.findAll('table')[39 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    year_built = listing.findAll('table')[40 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    ownership = listing.findAll('table')[40 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    floor_plan = listing.findAll('table')[41 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    views = listing.findAll('table')[41 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    misc = listing.findAll('table')[42 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    pets = listing.findAll('table')[42 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    laundry = listing.findAll('table')[43 + VT].findAll('td')[1].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()
    possession = listing.findAll('table')[43 + VT].findAll('td')[3].contents[0].replace("$","").replace(",","").replace('\xa0','empty').strip()

    results5 = {
        "waterfront":waterfront,
        "garage":garage,
        "life_style":life_style,
        "heating":heating,
        "cooling":cooling,
        "fireplace":fireplace,
        "basement_features":basement_features,
        "building_amenities":building_amenities,
        "maintenance_included":maintenance_included,
        "appliances_included":appliances_included,
        "year_built":year_built,
        "ownership":ownership,
        "floor_plan":floor_plan,
        "views":views,
        "misc":misc,
        "pets":pets,
        "laundry":laundry,
        "possession":possession
    }
    return dict(**results1,
                **results2,
                **results3,
                **results4,
                **results5,
                **get_box_vals(listing),
                image_urls="||".join(get_thumbnail_urls(listing))
               )

def main():
    url = parser.parse_args().url
    remote_selenium = parser.parse_args().selenium 
    print (f"You Entered the url: {url}\nSelenium URI: {remote_selenium}")
    
    gprint("Connecting To remote selenium-server...")
    driver = webdriver.Remote(remote_selenium, webdriver.DesiredCapabilities.CHROME)

    # load mls listing page
    driver.get(url)
    gprint("Verifying page title - this may take a moment..,\n")
    sleep(10)
    assert driver.title == 'Dashboard | Collab Center'
    bprint("Initial MLS page loaded.")
    
    # get link and load printable reports page
    
    #printable_reports_url = get_printable_reports_url(driver)
    #driver.get(printable_reports_url)
    open_printable_reports_page(driver)
    gprint("10 Second sleep while page loads...\n")    
    #sleep(10)
    assert driver.title == 'Customer Report'
    
    bprint("Successfully loaded Printable Reports page:\n{}".format(driver.current_url))
    
    # prime beautiful soup
    soup = get_soup(driver)
    
    gprint("Acquiring Housing data...")
    
    housing_df = pd.DataFrame({})
    
    for i in range(get_listing_total(soup)):
        print (f"Acquiring Data for Listing {i}...")
        listing_temp = get_listing_entry(i,soup)
        temp_df = pd.DataFrame(get_results(listing_temp,driver),index=[i])
        housing_df = housing_df.append(temp_df)
    
    gprint("Data Acquisition Complete")
    
    #print ("Deleting prior records from temp table...")
    #query = """
    #    #standardSQL
    #    DELETE housing.mls_tmp
    #    WHERE TRUE;"""
    #client.query(query)
    
    print ("Preping data for BigQuery...")
    #dataset_id = 'housing'
    #table_id = 'mls_tmp'
    #table_ref = client.dataset(dataset_id).table(table_id)
    #table = client.get_table(table_ref)
    
    insert_rows = []
    for _, \
    bedrooms,  \
    full_baths, \
    half_baths, \
    master_bath, \
    for_lease, \
    tax_condo_num, \
    taxes, \
    approx_lot_dimensions, \
    sewer, \
    water_source, \
    style, \
    sub_Style, \
    monthly_maintenance, \
    maintenance_includes, \
    ground_floor, \
    elementary_school, \
    first_floor, \
    jr_highschool, \
    second_floor, \
    high_school, \
    third_floor, \
    basement, \
    assessments, \
    municipal_assessment, \
    easements, \
    items_included, \
    items_not_included, \
    building_complex, \
    unit_num, \
    model_line, \
    approx_unit_sqtf, \
    underlying_mtg, \
    yrs_remaining, \
    number_of_shares, \
    number_of_stories, \
    stairs, \
    building_assoc_charges, \
    board_finance_requirements, \
    management_company, \
    management_phone, \
    waterfront, \
    garage, \
    life_style, \
    heating, \
    cooling, \
    fireplace, \
    basement_features, \
    building_amenities, \
    maintenance_included, \
    appliances_included, \
    year_built, \
    ownership, \
    floor_plan, \
    views, \
    misc, \
    pets, \
    laundry, \
    possession, \
    last_price, \
    ml_num, \
    address, \
    town, \
    zipcode, \
    county, \
    county_locale, \
    areacode, \
    direct, \
    original_lp, \
    days_on_mkt, \
    image_urls in housing_df.itertuples():
        insert_rows.append((f"TIMESTAMP('{TODAY}')",
                           str(bedrooms).replace('"','').replace("'",'') ,
                            str(full_baths).replace('"','').replace("'",''),
                            str(half_baths).replace('"','').replace("'",''),
                            str(master_bath).replace('"','').replace("'",''),
                            str(for_lease).replace('"','').replace("'",''),
                            str(tax_condo_num).replace('"','').replace("'",''),
                            str(taxes).replace('"','').replace("'",''),
                            str(approx_lot_dimensions).replace('"','').replace("'",''),
                            str(sewer).replace('"','').replace("'",''),
                            str(water_source).replace('"','').replace("'",''),
                            str(style).replace('"','').replace("'",''),
                            str(sub_Style).replace('"','').replace("'",''),
                            str(monthly_maintenance).replace('"','').replace("'",''),
                            str(maintenance_includes).replace('"','').replace("'",''),
                            str(ground_floor).replace('"','').replace("'",''),
                            str(elementary_school).replace('"','').replace("'",''),
                            str(first_floor).replace('"','').replace("'",''),
                            str(jr_highschool).replace('"','').replace("'",''),
                            str(second_floor).replace('"','').replace("'",''),
                            str(high_school).replace('"','').replace("'",''),
                            str(third_floor).replace('"','').replace("'",''),
                            str(basement).replace('"','').replace("'",''),
                            str(assessments).replace('"','').replace("'",''),
                            str(municipal_assessment).replace('"','').replace("'",''),
                            str(easements).replace('"','').replace("'",''),
                            str(items_included).replace('"','').replace("'",''),
                            str(items_not_included).replace('"','').replace("'",''),
                            str(building_complex).replace('"','').replace("'",''),
                            str(unit_num).replace('"','').replace("'",''),
                            str(model_line).replace('"','').replace("'",''),
                            str(approx_unit_sqtf).replace('"','').replace("'",''),
                            str(underlying_mtg).replace('"','').replace("'",''),
                            str(yrs_remaining).replace('"','').replace("'",''),
                            str(number_of_shares).replace('"','').replace("'",''),
                            str(number_of_stories).replace('"','').replace("'",''),
                            str(stairs).replace('"','').replace("'",''),
                            str(building_assoc_charges).replace('"','').replace("'",''),
                            str(board_finance_requirements).replace('"','').replace("'",''),
                            str(management_company).replace('"','').replace("'",''),
                            str(management_phone).replace('"','').replace("'",''),
                            str(waterfront).replace('"','').replace("'",''),
                            str(garage).replace('"','').replace("'",''),
                            str(life_style).replace('"','').replace("'",''),
                            str(heating).replace('"','').replace("'",''),
                            str(cooling).replace('"','').replace("'",''),
                            str(fireplace).replace('"','').replace("'",''),
                            str(basement_features).replace('"','').replace("'",''),
                            str(building_amenities).replace('"','').replace("'",''),
                            str(maintenance_included).replace('"','').replace("'",''),
                            str(appliances_included).replace('"','').replace("'",''),
                            str(year_built).replace('"','').replace("'",''),
                            str(ownership).replace('"','').replace("'",''),
                            str(floor_plan).replace('"','').replace("'",''),
                            str(views).replace('"','').replace("'",''),
                            str(misc).replace('"','').replace("'",''),
                            str(pets).replace('"','').replace("'",''),
                            str(laundry).replace('"','').replace("'",''),
                            str(possession).replace('"','').replace("'",''),
                            str(last_price).replace('"','').replace("'",''),
                            str(ml_num).replace('"','').replace("'",''),
                            str(address).replace('"','').replace("'",''),
                            str(town).replace('"','').replace("'",''),
                            str(zipcode).replace('"','').replace("'",''),
                            str(county).replace('"','').replace("'",''),
                            str(county_locale).replace('"','').replace("'",''),
                            str(areacode).replace('"','').replace("'",''),
                            str(direct).replace('"','').replace("'",''),
                            str(original_lp).replace('"','').replace("'",''),
                            str(days_on_mkt).replace('"','').replace("'",''),
                            str(image_urls).replace('"','').replace("'",'')))
        
    #errors = client.insert_rows(table, insert_rows)  # API request - runs streaming insert
    #assert errors == []
    
    VALUES_STRING = str(insert_rows)[1:-1]
    gprint(" Insert results to Time Partitioned table - housing.mls")
    query = \
"""#standardSQL
INSERT INTO housing.mls
(_PARTITIONTIME,
    bedrooms,
    full_baths,
    half_baths,
    master_bath,
    for_lease,
    tax_condo_num,
    taxes,
    approx_lot_dimensions,
    sewer,
    water_source,
    style,
    sub_Style,
    monthly_maintenance,
    maintenance_includes,
    ground_floor,
    elementary_school,
    first_floor,
    jr_highschool,
    second_floor,
    high_school,
    third_floor,
    basement,
    assessments,
    municipal_assessment,
    easements,
    items_included,
    items_not_included,
    building_complex,
    unit_num,
    model_line,
    approx_unit_sqtf,
    underlying_mtg,
    yrs_remaining,
    number_of_shares,
    number_of_stories,
    stairs,
    building_assoc_charges,
    board_finance_requirements,
    management_company,
    management_phone,
    waterfront,
    garage,
    life_style,
    heating,
    cooling,
    fireplace,
    basement_features,
    building_amenities,
    maintenance_included,
    appliances_included,
    year_built,
    ownership,
    floor_plan,
    views,
    misc,
    pets,
    laundry,
    possession,
    last_price,
    ml_num,
    address,
    town,
    zipcode,
    county,
    county_locale,
    areacode,
    direct,
    original_lp,
    days_on_mkt,
    image_urls)
VALUES {value}""".format(value=VALUES_STRING).replace('"','')
    client.query(query)
    
    bprint("Done!")
    driver.close()
    sys.exit(1)
        
if __name__ == "__main__":
    main()
