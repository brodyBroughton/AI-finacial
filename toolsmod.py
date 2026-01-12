"""Utility helpers for working with cached EDGAR filings."""

import json
import os

from edgar import Company


## tools
def cache_fetcher(ticker: str, cache_dir: str = "cache"):
    """Return cached Item 2 data for ``ticker`` if a local snapshot exists."""

    if not ticker:
        return None
    search_term = ticker.lower()
    cache_list = []
    try:
        for item in os.listdir(cache_dir):
            full_path = os.path.join(cache_dir, item)
            if os.path.isfile(full_path) and search_term in item.lower():
                cache_list.append(item)
    except FileNotFoundError:
        return None

    if not cache_list:
        return None

    cache_list.sort()
    filename = cache_list[-1]
    stockinfo = filename.split('_')
    if len(stockinfo) >= 3:
        stockinfo[2] = stockinfo[2].replace(".json", "")

    with open(f"{cache_dir}/{filename}", 'r') as f:
        tenq = json.load(f)
    tenqitem2 = tenq['item 2']
    tenqitem2cont = tenqitem2['contents']

    return tenqitem2cont, stockinfo

def edgar_fetcher(ticker: str, filing_date: str | None = None):
    """Fetch a 10-Q via ``edgar`` and return Item 2 data without prompts."""

    if not ticker:
        return None
    ticker = ticker.lower()
    app = Company(ticker)
    forms = app.get_filings(form="10-Q")

    if filing_date:
        latest10q = None
        for filing in forms:
            if str(filing.filing_date) == filing_date:
                latest10q = filing
                break
        if latest10q is None:
            latest10q = forms.latest()
    else:
        latest10q = forms.latest()
    try:
        tenq = latest10q.obj()
    except:
        print(f"no 10-Q documents found in {ticker} this company is not supported under edgartools")
        return
    tenqitems = tenq.items
    
    #print(tenqitems)
    
    #item = tenqitems[1]
    #tenqcontent = tenq[item]

    item1 = tenqitems[0]
    item2 = tenqitems[1]
    item3 = tenqitems[2]
    item4 = tenqitems[3]
    item5 = tenqitems[4]
    item6 = tenqitems[5]
    tenqjson = {
        "ticker" : ticker,
        "form" : latest10q.form,
        "item 1" : {
            "item name" : tenqitems[0],
            "contents" : tenq[item1],
        },
        "item 2" : {
            "item name" : tenqitems[1],
            "contents" : tenq[item2],
        },
        "item 3" : {
            "item name" : tenqitems[2],
            "contents" : tenq[item3],
        },
        "item 4" : {
            "item name" : tenqitems[3],
            "contents" : tenq[item4],
        },
        "item 5" : {
            "item name" : tenqitems[4],
            "contents" : tenq[item5],
        },
        "item 6" : {
            "item name" : tenqitems[5],
            "contents" : tenq[item6],
        },


    }
    
    tenqitem2 = tenqjson['item 2']
    tenqitem2cont = tenqitem2['contents']
    
    stockinfo = []
    # Provide a lightweight tuple so callers can surface the company name,
    # form type, and filing date alongside the textual content.
    stockinfo += (f"{latest10q.company}"), (f"{latest10q.form}"), (f"{latest10q.filing_date}")
    return tenqitem2cont, stockinfo
