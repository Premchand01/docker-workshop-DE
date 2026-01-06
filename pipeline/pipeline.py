import sys
import pandas as pd
print("arguments",sys.argv)

print("hello Pipeline")

month=int(sys.argv[1])
#df = pd.DataFrame({"A":[1,2],"B":[3,4]})
df=pd.DataFrame({"day":[1,2],"num_passengers":[3,4]})
df['month']= month

print(df)
#day=int(sys.argv[1])
#print(f" Running pipeline for the day {day}")