#Recursive data structure to represent the tree or graph heirarchy in the structure of Git repo
#CurrDir => The current directory which is represented by this DirTree object
#CurrDirHash => The hash of the current directory generated from its contents
#DirTreeLst => A exhaustive list of all the folders present directly under the current directory
#FileHashMap => A mapping from the list of all the files present in the current directory to their respective hashes
class DirTree:
	def __init__(self, currDir=""):
		self.CurrDir = currDir
		self.CurrDirHash = ""		
		self.DirTreeLst = []
		self.FileHashMap = {}