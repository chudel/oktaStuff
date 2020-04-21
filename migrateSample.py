#!/usr/bin/python3
# 
# This is a sample python3 script that takes a TAB separated plaintext file and uses the API
# to create users, populate a migrated bcrypt password, and (optionally) migrate a prexisting
# custom TOTP token that has already been configured in the system.
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
factorId = '{Your FactorID if applicable}' 					# Custom TOTP Token Identifier (unique per custom token/tenant)

debug = False                                               # if Debug Mode - set the email, TOTP, and password values as below
loginPrefix = "test_"                                       # added to login name for testing. set to "" for production
debugEmail = "{yourcontactemail@yourdomain.com}"            # used instead of actual email address
debugTOTP = "IF3TAYK6KRQXI3B7IYSDSUK3GQ"                    # debug TOTP secret, to get predicable otp values
debugHash = "$2b$10$wecbrFjGyP39IfRraumgt.1efpd1eRng4Mzr8EES/TwYqaewUeoK2" # Debug Bcrypt value for password, 'password'


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

    # return 0   # Uncomment if you want only to run the validaton
    #
    # Import the TSV file (with a header row)
    # 
    with open(infile, encoding='utf-8', errors='ignore') as tsvfile:
       reader = csv.DictReader(tsvfile, dialect='excel-tab')

	   # Use Threads to parallelize much of the create user work and make it process more quickly
	   # See below for concerns regarding API threshold limits
	   #
       with concurrent.futures.ThreadPoolExecutor(max_workers=9) as executor:
          futureCreateUser = {executor.submit(createUser,row): row for row in reader}
          for future in concurrent.futures.as_completed(futureCreateUser):
             url = futureCreateUser[future]
             try:
               data = future.result()
             except Exception as exc:
               print('%r generated an exception: %s' % (url, exc))


    return 0

def createUser(row):
   # Adds a user. Returns 1 (Success), 0 (Fail), -1 (User Already Exists)
   #
   Status = 0

 
   conn = http.client.HTTPSConnection(apiHost)   # Set this up once?
   # Parse row for necessary values
   phone = row['VOICE']
   mobile = row['MOBILE']
   ext = row['VOICE_EXT']
   totp = row['TOTP']
   pwd = debugHash if debug else row['PWD'] 
   email = row['EMAIL']
   user = row['USER']
   fname = row['FIRST_NAME']
   lname = row['LAST_NAME']

   if not len(fname):
      fname = "First"

   if not len(lname):
      lname = "Last"

   firstName = loginPrefix + fname
   lastName = loginPrefix + lname 

   # parse Bcrypt value for WorkFactor, Salt, and Hash Values
   workProduct = int(pwd[4:6])
   hashSalt = pwd[7:29]
   hashValue = pwd[29:]


   # if extension exists, add it to phone number
   if (len(ext) > 1):
      phone = phone + " ext. " + ext

   headers = {
     'Accept': 'application/json',
     'Content-Type': 'application/json',
     'Authorization': apiAuth,
   }

   # Create a JSON Payload
   payload = {
      "profile": {
         "firstName": firstName,  # Replace with FirstName when Data exists
         "lastName": lastName,    # Replace with LastName when Data exists
         "email": debugEmail if debug else email,
         "mobilePhone": mobile,
         "primaryPhone": phone,
       "login": "" +  loginPrefix + user,
      },
      "credentials": {
          "password" : { 
             "hash": {
                 "algorithm": "BCRYPT",
                 "workFactor": workProduct,
                 "salt": hashSalt,
                 "value": hashValue 
             }
          }
       }
   }
   jsonPayload = json.dumps(payload)

   
   conn.request("POST", "/api/v1/users?activate=true", jsonPayload, headers)
   res = conn.getresponse()

   # Send Request and get status. Parse for remaining API calls.
   rStatus = res.status
   
   # Immediately check for Forbidden status, abort if necessary
   if (rStatus == 401):
      print("%s - Forbidden Response. User not created. Is API Token correct?" % (loginPrefix + user))
      status = 0
      return status

   RateLimitRemaining = int(res.headers["X-Rate-Limit-Remaining"]) 
   RateLimitReset = int(res.headers["X-Rate-Limit-Reset"])

   data = res.read()

   if (RateLimitRemaining) < 11:    # Only 11 API calls are left. A small buffer over the thread count which is set at 9
      print ("Rate Limit: %d left" % (RateLimitRemaining))
      if (RateLimitReset - int(time.time())) > 1:  # If we haven't already 'run out the clock'
         print("WARN: API requests/second limit reached. Waiting %d seconds." % (RateLimitReset - int(time.time())))
         time.sleep(2 + RateLimitReset - int(time.time()))  # Sleep until the RateLimitReset time has occured + 1 second
         print("wakeup ...")
      else:
          time.sleep(1)

   jResponse = json.loads(data.decode("utf-8"))
 
   if (rStatus == 200):                       #  OK
      print("%s - User Created" % (loginPrefix + user), flush=True)
      userId = jResponse['id']
      if len(totp) > 8:                       # Add TOTP Token if user was created
         tStatus = addTotp(loginPrefix + user,userId,totp)
      status = 1
   elif (rStatus == 400):                     #  Error
      if re.match(r".*already exists.*", str(jResponse['errorCauses'])) != None:
         print("%s - User Already Exists. User Not Created / Updated" % (loginPrefix + user))
         status = -1
   else:
      print("%s - Unknown Status - Return Code %d / Data Returned %s" % (loginPrefix + user,rStatus,jResponse))
      status = 0 

   return Status



def addTotp(username,userid,totp):   # Adds Custom TOTP token to associated userID

   status = 0
   headers = {
     'Accept': 'application/json',
     'Content-Type': 'application/json',
     'Authorization': apiAuth,
   }

   payload = {
     "factorType": "token:hotp",
     "provider": "CUSTOM",
     "factorProfileId": factorId,
           "profile": {
                 "sharedSecret":  totp
                   }
   }
   
   conn = http.client.HTTPSConnection(apiHost)   
   jsonPayload = json.dumps(payload)
   conn.request("POST", "/api/v1/users/" + userid + "/factors?activate=true", jsonPayload, headers)
   res = conn.getresponse()

   rStatus = res.status
   data = res.read()

   jResponse = json.loads(data.decode("utf-8"))
 
   if (rStatus == 200):                       #  OK
      print("%s - User Added custom TOTP token" % (username))
      status = 1
   else:
      print("%s - Unknown Status - Return Code %d / Data Returned %s" % (loginPrefix + user,rStatus,jResponse))
      status = 0 
   

#   print(jResponse)
   return status

    

def validate(infile):
    # Validate the contents of TSV file do not contain errors.
    # Checks for phone-number format only in the VOICE VOICE_EXT and MOBILE columns
    # Checks for email-address format only in the EMAIL Column
    # Checks for Base32 format only in the TOTP column
    # Checks for Bcrypt format only in the PWD column
    # Checks for username format only in the USER volumn

    status = True
    dupList = [] # Check for Duplicates at the end of processing

    phonePattern = r'^[+]*[(]{0,1}[0-9]{1,4}[)]{0,1}[-\s\./0-9]*$'
    numPattern = r'^[#]{0,1}[0-9]{0,8}$' # up to 8 Digit Extension
    b32Pattern = r'^[A-Z2-7]+=*$'

    emailPattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    bcryptPattern = r'^\$2[ayb]\$[0-9]{2}\$.{53}$'
	
	# Username must be between 3-20 characters, composed only of alphanumeric and @,+,_,.,-
    userPattern = r'^[a-zA-Z0-9@+_.-]{3,20}$' 

    lineno = 0; # Tracking Line Number / ROW in the TSV file

    # Import the TSV file (with a header row)
	# The following HEADER values MUST BE PRESENT: TOTP, VOICE,VOICE_EXT, MOBILE,EMAIL, USER, FIRST_NAME, LAST_NAME, PWD
    # 
    with open(infile, encoding='utf-8', errors='ignore') as tsvfile:
       reader = csv.DictReader(tsvfile, dialect='excel-tab')

       if(
          len(reader.fieldnames) != 9 
          or not reader.fieldnames.count('TOTP')
          or not reader.fieldnames.count('VOICE')
          or not reader.fieldnames.count('VOICE_EXT')
          or not reader.fieldnames.count('MOBILE')
          or not reader.fieldnames.count('EMAIL')
          or not reader.fieldnames.count('USER')
          or not reader.fieldnames.count('FIRST_NAME')
          or not reader.fieldnames.count('LAST_NAME')
          or not reader.fieldnames.count('PWD')
          ):
             print("File does not contain exactly 9 fields OR one or more filedname titles appear incorrect.")
             return False

       for row in reader:

          lineno = lineno + 1

          fname = row['FIRST_NAME']
          lname = row['LAST_NAME']
          phone = row['VOICE']
          mobile = row['MOBILE']
          ext = row['VOICE_EXT']
          totp = row['TOTP']
          pwd = row['PWD']
          email = row['EMAIL']
          user = row['USER']
          user = re.sub(r' $',"",user)  # Remove space characters if present, convert to underscore
          user = re.sub(r' ',"_",user)

		  # add entry for later check for Duplicates.
          dupList.append(user)

          # Perform regex matches 
          phoneMatch = re.match(phonePattern,phone)
          mobileMatch = re.match(phonePattern,mobile) 
          extMatch = re.match(numPattern,ext)
          totpMatch = re.match(b32Pattern,totp)
          pwdMatch = re.match(bcryptPattern,pwd)
          emailMatch = re.match(emailPattern,email)
          userMatch = re.match(userPattern,user)
          
          # Check for matches, ignore if value is blank [for some optional values]

          if len(phone): 
             if phoneMatch == None:
                print("%6d: WARN %s Phone does not match format '%s'. Continuing ... " % (lineno, row['USER'], phone))

          if len(mobile):
             if mobileMatch == None:
                print("%6d: WARN %s Mobile does not match format '%s'. Continuing ..." % (lineno, row['USER'], mobile))

          if len(ext): 
             if extMatch == None:
                print("%6d: WARN %s Extension does not match format '%s'. Continuing ... " % (lineno, row['USER'], ext))

          if not len(fname):
                print("%6d: WARN %s no First Name. Setting First name to 'First'. Continuing ... " % (lineno,row['USER']))

          if not len(lname):
                print("%6d: WARN %s no Last Name. Setting Last name to 'Last'. Continuing ..." % (lineno,row['USER']))

          if len(totp): 
             if totpMatch == None:
                print("%6d: %s TOTP does not match format '%s' " % (lineno, row['USER'],totp))
                status = False

          if pwdMatch == None:
             print("%6d: %s Password does not match format '%s' " % (lineno, row['USER'], pwd))
             status = False

          if emailMatch == None:
             print("%6d: %s email does not match format '%s' " % (lineno,row['USER'], email))
             status = False

          if userMatch == None:
             print("%6d: %s user does not match format '%s' " % (lineno, row['USER'],user))
             status = False

    duplicates = findDuplicates(dupList)
    if len(duplicates) > 0:
       print("The following %d duplicates were found: %s. " %(len(duplicates),duplicates))
       #status = False   # Do not migrate if there are duplicates.
       status = True     # NON-PROD-USE-ONLY. We will migrate just one of the duplicates (the first one -- the others will error)

    print("%d rows processed" % (lineno))

    return status

def findDuplicates(seq):
   seen = set()
   seen_add = seen.add

   seen_twice = set (x for x in seq if x in seen or seen_add(x) )
   return list(seen_twice)

main()
