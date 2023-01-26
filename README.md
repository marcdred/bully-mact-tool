# bully-mact-tool
A tool to edit Bully's CAT files.  
It converts Bully's CAT files into MACT files (a customized version of Bully's ACT files) and converts MACT files back into CAT files.  
Created by marcdred, more information @ Bully Modding Discord.  
Extra thanks to vegasfest for helping me test and debug this tool.  

* Instructions for CAT_TO_MACT.py:  
	* You can generate MACT files from CAT files by running:   
		* `python3 CAT_TO_MACT.py YourCatFile.cat`  

* Instructions for MACT_TO_CAT.py:  
	* You can generate CAT files from MACT files by running:  
		* `python3 MACT_TO_CAT.py YourMactFile.mact`  
	* You can enable parameter optimization by running:
		* `python3 MACT_TO_CAT.py --po YourMactFile.mact`  

* Instructions for template files:  
	* CAT_TO_MACT will check for the existence of files named "TEMPLATES_CONDITIONS.txt" and "TEMPLATES_TRACKS.txt"  
	* You can generate TEMPLATE FILES by running:  
		* `python3 CAT_TO_MACT.py --GENERATE-TEMPLATES "C:\path\to\folder\with\all\cat\files"`  
	* You can tweak these templates by changing the names and types and CAT_TO_MACT will use that information when generating MACT files.  