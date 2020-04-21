#!/usr/bin/python3
# 
# This is a sample python3 script that takes a TAB separated plaintext file and uses the API
# to delete users.  If users were created with a login prefix (see:migrateSample.py), it will
# add it here to delete the user appropriately. 
#
import sys
import csv
import re
import http.client
import json
import mimetypes
import time
import concurrent.futures

## Global Variables ##
##

# Config Values
apiHost = "{Your Tenant}.oktapreview.com"					# api HostName
apiAuth = 'SSWS {Your API Token Here}' 						# api Authorization Header value
loginPrefix = "test_"										# Username prefix to add (if used during user create)

def main():
    """ Main program """
    if (len(sys.argv) != 2):
       print('Usage: ' +  sys.argv[0] + ' file.tsv - to migrate contents of file.tsv to okta.')
       print('     : The program must first be edited to modify several constant values.')
       return 0

    infile = sys.argv[1]

    # Validate TSV file values (with a header row)
    if (validate(infile) == False):
       print ("Validation FAILED. Please fix file before continuing.")
       return -1

    # Import the TSV file (with a header row)
    # 
    with open(infile, encoding='utf-8', errors='ignore') as tsvfile:
       reader = csv.DictReader(tsvfile, dialect='excel-tab')

	   # Use Threads to parallelize much of the create user work and make it process more quickly
	   # See below for concerns regarding API threshold limits
	   #
       with concurrent.futures.ThreadPoolExecutor(max_workers=9) as executor:
          futureDeleteUser = {executor.submit(deleteUser,row): row for row in reader}
          for future in concurrent.futures.as_completed(futureDeleteUser): 
                  url = futureDeleteUser[future]
                  try:
                     data = future.result()
                  except Exception as exc:
                     print('%r generated an exception: %s' % (url, exc))

    return 0

def deleteUser(row):
   # Adds a user. Returns 1 (Success), 0 (Fail), -1 (User Already Exists)
   #
   Status = 0

   conn = http.client.HTTPSConnection(apiHost)   # Set this up once?
   # Parse row for necessary values
   user = row['USER']

   headers = {
     'Accept': 'application/json',
     'Content-Type': 'application/json',
     'Authorization': apiAuth,
   }

   uri = "/api/v1/users/" + loginPrefix + user + "/lifecycle/deactivate"

   payload = {}
   jsonPayload = json.dumps(payload)

#   print(json.dumps(jsonPayload))
#   return 0
   
   conn.request("POST", uri,jsonPayload, headers)

   res = conn.getresponse()

   rStatus = res.status
      
   # Immediately check for Forbidden status, abort if necessary
   if (rStatus == 401):
      print("%s - Forbidden Response. User not deactivated or deleted. Is API Token correct?" % (loginPrefix + user))
      status = 0
      return status

   RateLimitRemaining = int(res.headers["X-Rate-Limit-Remaining"]) 
   RateLimitReset = int(res.headers["X-Rate-Limit-Reset"])

   data = res.read()

   if (RateLimitRemaining) < 11:    # Only 11 API calls are left
      if (RateLimitReset - int(time.time())) > 1:  # If we haven't already 'run out the clock'
         print("WARN: API requests/second limit reached. Waiting %d seconds." % (RateLimitReset - int(time.time())))
         time.sleep(2 + RateLimitReset - int(time.time()))  # Sleep until the RateLimitReset time has occured + 2 second
         print("wakeup ...")
      else:
         print("WARN: API requests/second limit reached. Waiting 1 second." )
         time.sleep(1)

   jResponse = json.loads(data.decode("utf-8"))

   if (rStatus >= 200 and rStatus < 299):                       #  OK
      try2 = conn.request("DELETE","/api/v1/users/" + loginPrefix + user,"",headers)
      throaway = conn.getresponse()
      throaway.read()
      rStatus2 = throaway.status
      if (rStatus2 != 204):  # (204) deleted
         print("%s - User Deactivated. Problem deleting.(Status %d)" % (loginPrefix + user,rStatus2), flush=True)
      else:   
         print("%s - User Deactivated + Deleted" % (loginPrefix + user), flush=True)
      status = 1
   elif (rStatus == 404):
      print("%s - User does not exist" % (loginPrefix + user))
   else:
      print("%s - Unknown Status - Return Code %d / Data Returned %s" % (loginPrefix + user,rStatus,jResponse))
      status = 0 

   return Status


def validate(infile):
    # Validate the contents of TSV file do not contain errors.
    # Checks for username format only in the USER volumn

    status = True

    userPattern = r'^[a-zA-Z0-9@+_.-]{3,20}$' 

    lineno = 0; # Tracking Line Number / ROW in the TSV file

    # Import the TSV file (with a header row)
    # 
    with open(infile, encoding='utf-8', errors='ignore') as tsvfile:
       reader = csv.DictReader(tsvfile, dialect='excel-tab')

       if(
          not reader.fieldnames.count('USER')
          ):
             print("File does not contain exactly a USER field.")
             return False

       for row in reader:

          lineno = lineno + 1

          user = row['USER']

          # Perform regex matches 
          userMatch = re.match(userPattern,user)
          
          # Check for matches, ignore if value is blank [for some optional values]
          if userMatch == None:
             print("%6d: user does not match format '%s' " % (lineno, user))
             status = False

    print("%d rows processed" % (lineno))

    return status

main()
