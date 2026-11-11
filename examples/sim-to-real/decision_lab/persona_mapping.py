"""Conservative common age/education bins; no invented fine-grained education."""
AGE_BANDS=['18-24','25-34','35-44','45-54','55-64','65-74','75-84','85+']
DEGREE={"Bachelor's degree",'Higher degree','Masters or higher','University of Applied Sciences/University of Education','University/ETH'}
NON_DEGREE={'Secondary school','High school','Lower degree (certificate or diploma)','Associate Degree or Certificate','Primary school','No formal education','Elementary school','Higher technical/vocational training','Apprenticeship/vocational school/commercial middle school','Obligatory schooling','Matura/vocational school-leaving certificate','None'}

def common_background(background,kind):
    education=background['education']
    if education in DEGREE:level='bachelor_or_higher'
    elif education in NON_DEGREE:level='below_bachelor'
    else:return None
    if kind=='dryer':age=background['age_band'].replace('85 or over','85+')
    elif kind=='swiss':
        raw=background['age_years']
        try:years=float(raw)
        except (ValueError,TypeError):return None
        if years<18:return None
        age=next((band for band,upper in zip(AGE_BANDS,[24,34,44,54,64,74,84,float('inf')]) if years<=upper),None)
    else:raise ValueError('Unknown reviewed adapter')
    if age not in AGE_BANDS:return None
    return {'age_bracket':age,'education_group':level}
