# oktaStuff
Miscellaneous Okta stuff, hopefully of some benefit - scripts, etc..

There are a number of migration scripts and tools already available, but I found some of them to be a bit _less modern_.  The scripts here are execute using Python3 and account for some intracacies in working with the API thresholds. This is of particular value when migrating a large number of users into Okta.

The following scripts have some elementary error checking.  I don't claim they are great, only that they worked, at least once. :) In these cases, modify the script with the API host and API Key as appropriate for your environment. 

## migrateSample.py
This is a sample migration script (launches 9 threads and respects API thresholds) that:
- Takes in a Tab Separated file (TSV) with header rows
- Validates the input for some of the fields values (such as Bcrypt password, Base32 TOTP Secret, email, etc..)
- Creates Users with migrated Bcrypt password credentials and (optionally) a custom TOTP value

````
./migrateSample.py mock_data.tsv
50 rows processed
test_mstratiff2 - User Created
test_gsarjant0 - User Created
test_dflewin4 - User Created
test_ccastagne1 - User Created
test_skoppke3 - User Created
test_lhooks8 - User Created
test_cgurwood5 - User Created
test_gwoodford6 - User Created
test_jjukubczak7 - User Created
test_dflewin4 - User Added custom TOTP token
test_mwilseya - User Created
test_brominov9 - User Created
test_jchungd - User Created
[...]
````

## deleteSample.py
This is a sample deletion script (launches 9 threads and respects API thresholds) that
- Takes in a TSV file with at least one header row of name "USER"
- Deactivates and then deletes users
````
 ./deleteSample.py mock_data.tsv
50 rows processed
test_jjukubczak7 - User Deactivated + Deleted
test_skoppke3 - User Deactivated + Deleted
test_cgurwood5 - User Deactivated + Deleted
test_gwoodford6 - User Deactivated + Deleted
test_mstratiff2 - User Deactivated + Deleted
test_lhooks8 - User Deactivated + Deleted
test_ccastagne1 - User Deactivated + Deleted
test_dflewin4 - User Deactivated + Deleted
test_gsarjant0 - User Deactivated + Deleted
test_brominov9 - User Deactivated + Deleted
test_mwilseya - User Deactivated + Deleted
test_dsolwayb - User Deactivated + Deleted
````


## mock_data.tsv
Sample mock data, created using the https://www.mockaroo.com/ website as a starting template.  **The User Information and Credentials in this file are NOT REAL**.   
