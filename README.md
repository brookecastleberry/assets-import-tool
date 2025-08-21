# assets-import-tool


#Architecture for Initial Load
#1. Manual: Export CSV from Essentials
#2. Manual: Customer fills out Application column, add in branch & file exclusion column
#3. Script to read the Application column and fill out in JSON acceptable by the API Import Tool step 2 to load in shell organizations
#4. Run Step 3 of Api Import Tool then replace fields with correct git orgs, repos, etc...maybe don't run api import tool but just generate it
#5. Run step 4 of api import tool or Script to create targets json and grab data from fields in csv file 
#6. Run last step of api import tool to load in targets to proper application organizations 


#Architecture for Additional Updates
#automatically identify & import new repos --> slack notification or email notification 
