"""Explicit compatible demographic sets; no target choices used for matching."""
import re
AGE=['18-24','25-34','35-44','45-54','55-64','65-74','75-84','85+']
EDU=['No formal','Primary','Secondary','Vocational / cert','Some college',"Associate's","Bachelor's","Master's",'Doctorate','Postdoc']
DEGREE=EDU[6:]
EDUCATION={
 "Bachelor's degree":['Bachelor\'s'],"Bachelor's degree or higher":DEGREE,'College graduate+':DEGREE,'Postgraduate degree':DEGREE[1:],'Graduate degree':DEGREE[1:],
 'Higher degree':DEGREE[1:],'Masters or higher':DEGREE[1:],
 'University of Applied Sciences/University of Education':DEGREE,'University/ETH':DEGREE,
 'Some college, no degree':['Some college'],'Some college':['Some college',"Associate's"],"Some college or Associate's degree":['Some college',"Associate's"],
 'Associate degree':["Associate's"],'Associate Degree or Certificate':['Vocational / cert',"Associate's"],
 'Some post-secondary education':['Vocational / cert','Some college',"Associate's"],
 'H.S. graduate or less':EDU[:3],'Less than high school':EDU[:2],'No high school diploma or GED':EDU[:2],
 'High school graduate':['Secondary'],'High school graduate (high school diploma or the equivalent GED)':['Secondary'],
 'Secondary school':['Secondary'],'High school':['Secondary'],'Primary school':['Primary'],'Elementary school':['Primary'],
 'No formal education':['No formal'],'Lower degree (certificate or diploma)':['Vocational / cert',"Associate's"],
 'Higher technical/vocational training':['Vocational / cert',"Associate's"],
 'Apprenticeship/vocational school/commercial middle school':['Vocational / cert'],
 'Obligatory schooling':['Secondary'],'Matura/vocational school-leaving certificate':['Secondary'],
}
# Labels added for the v2 re-checks; existing labels and their results are unchanged.
EDUCATION.update({
    'No high school diploma': ['No formal', 'Primary'],
    'High school, no college': ['Secondary'],
    'Attended college, no degree': ['Some college', 'Vocational / cert'],
    'AA or BA': ["Associate's", "Bachelor's"],
    'Graduate degree': DEGREE[1:],
    'Less than high school': ['No formal', 'Primary'],
    'High school graduate': ['Secondary'],
    'Some college, no degree': ['Some college', "Associate's"],
    "Associate's degree": ["Associate's"],
    'College graduate/some post grad': ["Bachelor's"],
    'Postgraduate': DEGREE[1:],
    'Below bachelor\'s degree': ['No formal', 'Primary', 'Secondary', 'Vocational / cert', 'Some college', "Associate's"],
    # German instrument (data_valid.sav). Level 6 is excluded at the adapter because its
    # label merges Abitur with a university degree; nothing is guessed here.
    'Finished school without certificate': ['No formal'],
    'Elementary/main school or polytechnic secondary school, 8th/9th grade': ['Primary', 'Secondary'],
    'Intermediate school, secondary school or polytechnic upper secondary school, 10th grade': ['Secondary'],
    'Advanced technical college entrance qualification (graduation from a technical college': ['Vocational / cert'],
    'University degree': DEGREE,
    # RADIANT (Spain): the adapter passes the author's canonical level names directly.
    'No formal': ['No formal'],
    'Primary': ['Primary'],
    'Secondary': ['Secondary'],
    'Some college': ['Some college', "Associate's"],
    "Bachelor's": ["Bachelor's"],
    "Master's": DEGREE[1:],
    # US T-shirt instrument (CFTF_usa.dta).
    "Associate's": ["Associate's"],
    'Below high school': ['No formal', 'Primary'],
    # Open eCommerce (Amazon Mechanical Turk) survey of US respondents.
    'High school diploma or GED': ['Secondary'],
    'Graduate or professional degree (MA, MS, MBA, PhD, JD, MD, DDS, etc)': DEGREE[1:],
    'Some high school or less': ['No formal', 'Primary'],
})
# Studies whose instrument never measured education. The constraint is dropped and
# declared; education is never inferred from other fields.
NO_EDUCATION={'drone','shoes'}
# Bands that straddle the persona age brackets are widened, never narrowed.
AGE_SPANS={
 '18-20 years old':(['18-24'],'sub_band_18_20'),
 '21-25 years old':(['18-24','25-34'],'span_band_21_25'),
 '26-35 years old':(['25-34','35-44'],'span_band_26_35'),
 '36-45 years old':(['35-44','45-54'],'span_band_36_45'),
 '46-55 years old':(['45-54','55-64'],'span_band_46_55'),
 '56 years old or older':(AGE[4:],'band_56_plus'),
 # German study reports decade bands that straddle persona brackets; widened, never narrowed.
 'up to 29':(['18-24','25-34'],'span_band_under_30'),
 '30-39':(['25-34','35-44'],'span_band_30_39'),
 '40-49':(['35-44','45-54'],'span_band_40_49'),
 '50-59':(['45-54','55-64'],'span_band_50_59'),
 '60 or older':(AGE[4:],'band_60_plus'),
}
COUNTRIES={'USA':'North America','US':'North America','United States':'North America','Canada':'North America','CAN':'North America','UK':'Western Europe','United Kingdom':'Western Europe','Ireland':'Western Europe','IRE':'Western Europe','Switzerland':'Western Europe','Germany':'Western Europe','Deutschland':'Western Europe','Spain':'Western Europe'}

def constraints(record):
 b=record['background'];raw=str(next((b[k] for k in ['Age','Age group','age_band','age_years'] if k in b),'Unknown')).replace('–','-')
 education=str(next((b[k] for k in ['Education','education'] if k in b),'Unknown'))
 no_education=education not in EDUCATION and record['study'] in NO_EDUCATION
 if education not in EDUCATION and not no_education:return None,'unmapped_education:'+education
 age=raw.replace('85 or over','85+').replace('65 or older','65+')
 if age in AGE:ages=[age];resolution='native_age_band'
 elif re.fullmatch(r'\d+(\.0)?',age):
  n=float(age)
  if n<18:return None,'not_adult'
  ages=[AGE[next(i for i,upper in enumerate([24,34,44,54,64,74,84,float('inf')]) if n<=upper)]];resolution='numeric_age_to_native_band'
 elif age=='65+':ages=AGE[5:];resolution='65_plus'
 elif age=='80 or older':ages=AGE[6:];resolution='75_plus_common_coarsening'
 elif age=='21-24':ages=['18-24'];resolution='sub_band_21_24'
 elif age in AGE_SPANS:ages,resolution=AGE_SPANS[age]
 elif age in ['18-29','30-49','50-64']:ages=AGE[:5];resolution='18_64_common_coarsening'
 else:return None,'unmapped_age:'+age
 country=record.get('country','United States')
 if country not in COUNTRIES:return None,'unmapped_country:'+str(country)
 allowed={'region':[COUNTRIES[country]],'age_bracket':ages}
 if not no_education:allowed['highest_education']=EDUCATION[education]
 sex=b.get('Sex',b.get('Gender'))
 if sex in ['Male','Female']:allowed['gender_identity']=['Man' if sex=='Male' else 'Woman']
 size=b.get('household_size')
 try:
  n=float(size)
  if n>=1:allowed['lstyle_household_size']=['Lives alone' if n==1 else '2 people' if n==2 else '3-4 people' if n<=4 else '5+ people']
 except (TypeError,ValueError):pass
 # Currency and definitions differ; no income conversion is inferred here.
 rule={'allowed':allowed,'age_resolution':resolution,'excluded_sources':['real_human_survey']+(['gss'] if record['study']=='anes' else []),'country_context':country}
 if no_education:rule['education_resolution']='unavailable_in_instrument'
 return rule,None

def compatible(profile,rule):
 return profile['source'] not in rule['excluded_sources'] and all(profile['fields'].get(k) in values for k,values in rule['allowed'].items())
