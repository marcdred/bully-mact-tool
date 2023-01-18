# bully-mact-tool
A tool to edit Bully's ACT files.

This is version 3.3.1 of Marcdred's bully-mact-tool.  
At the moment I am learning git and plan on cleaning up this code in the future, please be patient.  
More information @ Bully Modding Discord or marcdred@outlook.com ( Beware that I rarely check this e-mail )  

* Instructions for CAT_TO_MACT.py:  
	* ".MACT" files are very similar to regular ACT files but with a few tweaks.  
	* You can generate MACT files by running:   
		* python3 CAT_TO_MACT.py YourCatFile.cat  
	* CAT_TO_MACT will check for the existence files named "TEMPLATES_CONDITIONS.txt" and "TEMPLATES_TRACKS.txt"  
	* You can generate TEMPLATE FILES by running:  
		* python3 CAT_TO_MACT.py --GENERATE-TEMPLATES "C:\path\to\folder\with\all\cat\files"  
	* You can tweak these templates by changing the names and types included there and CAT_TO_MACT   
	* will use that information whhen generating your MACT files.  
* Instructions for MACT_TO_CAT.py:  
	* You can generate CAT files by running:  
		* python3 MACT_TO_CAT.py YourMactFile.mact  

Extra thanks to vegasfest for helping me test and debug this tool.  