# Git as a Graph: Implementation

# The below code is an attempt to implement the core features of git emphasizing on its graph like nature. Please note that the operations implemented here are in the same
# 'spirit' as their git counter-parts but would likely differ in their details. They are similar enough to understand the concepts yet different since concerns such as performance,
# code maintainability and other aspects were not considered while implementing them. One can observe an extensive use of recursion and operations like map, filter and reduce and almost no uses of
# explicit loops. This is a conscious choice and I have laid out the benefits of this approach on my blog post of functional programming. (thepretendprogrammer.azurewebsites.net/index.php/2017/08/04/why-go-functional/)
import os
import zlib
import sys
from DirTree import DirTree
from hashlib import sha1

#The list of all folders that are created as part of git init operation. 
folderLst = ['branches', 'hooks', 'info', 'logs', 'objects\\info', 'objects\\pack', 'refs\\heads', 'refs\\tags']

#The list of all the files (with relative path) created with the git init operation along with their corresponding content stored as a list of lists.
fileLstWithContent = [['config', '[core]\n\trepositoryformatversion = 0\n\tfilemode = false\n\tbare = false\n\tlogallrefupdates = true\n\tsymlinks = false\n\tignorecase = true\n\thideDotFiles = dotGitOnly\n'],
					['description', 'Unnamed repository; edit this file \'description\' to name the repository.\n'],
					['HEAD', 'ref: refs\\heads\\master'],
					['info\\exclude', "# git ls-files --others --exclude-from=.git/info/exclude\n# Lines that start with '#' are comments.\n# For a project mostly in C, the following would be a good set of\n# exclude patterns (uncomment them if you want to use them):\n# *.[oa]\n# *~\n"]
					]
#Setting a global variable representing the base directory of the project					
currDir = os.getcwd()

# Helper Functions
#Checks if the index files exist in the .git directory
def indexFileExists():
    return os.path.isfile(os.path.join(currDir, ".git", "index"))

#Creates a new directory with the specified name only if the directory does not already exist
def checkAndCreateDir(dirPath):
	if not os.path.isdir(dirPath):
		os.makedirs(dirPath)

#Deletes the specified file only if the file exists
def deleteFileIfExists(fPath):
	if os.path.isfile(fPath):
		os.remove(fPath)

#Write content to the specified file
def writeToFile(file, content, mode):
	if not os.path.isfile(file):
		try:
			dirc = os.path.split(file)[0]
			checkAndCreateDir(dirc)
		except:
			return
	with open(file, mode) as f:
		f.write(content)

#Read content from the provided filename
def readFromFile(fileName, readMode='r'):
	content = ""
	with open(fileName, readMode) as f:
		content = f.read()
	return content

#Read content from the provided filename (using all available file modes) and decrypt its content using zlib library
def readFromFileAndDecompress(fileName):
	content = ""
	try:
		content = readFromFile(fileName, 'r')
		return zlib.decompress(content)
	except:
		try:
			content = readFromFile(fileName, 'rb')
			return zlib.decompress(content)
		except:
			try:
				content = readFromFile(fileName, 'rb')
				content = content.replace("\r\n", "\n")
				return zlib.decompress(content)
			except:
				return content

#Get the root directory of provided file path
def getRootDirectoryName(path):
	return path[ : path.index("\\")]

#Get the file and folder contents of the provided directory
def getDirectoryContents(dirContentLst):
	return map(lambda x: x[x.index("\\") + 1: ], dirContentLst)

#Create a tuple of list of files and list of folders from a combined list of the two
def separateFilesAndFolder(contentLst):
	fileLst = filter(lambda x: x.find("\\") == -1, contentLst)
	folderLst = filter(lambda x: x.find("\\") != -1, contentLst)
	return (fileLst, folderLst)

#Group sub-directories on the basis of their root directories in a key-value pair collection
def groupSubDirectories(dirLst):
	folderDict = {}
	mapFunc = lambda y: folderDict[getRootDirectoryName(y)].append(y) if (getRootDirectoryName(y) in folderDict) else (folderDict.setdefault(getRootDirectoryName(y), [y]))
	map(mapFunc, dirLst)
	return folderDict

#Generate a mapping from filename(fullPath or relativePath depending on the flag passed) to (fileHash, fileLastModifiedTime) for each entry in the index file
def getIndexFileHashMTimeMapping(keepFullPath=False):
	if not indexFileExists():
		return {}
	idxDict = {}
	fileContent = readFromFile(os.path.join(currDir, ".git", "index")).split("\n")[:-1]
	splitFileContent = map(lambda x: (x.split("\x00")[4], x.split("\x00")[2], x.split("\x00")[5]), fileContent)	
	if keepFullPath:
		fileToHashMapFunc = lambda x: idxDict.setdefault(x[0], (x[1], x[2]))
	else:
		fileToHashMapFunc = lambda x: idxDict.setdefault(os.path.split(x[0])[1], (x[1], x[2]))
	map(fileToHashMapFunc, splitFileContent)	
	return idxDict

#Generate a mapping from filename(fullPath or relativePath depending on the flag passed) to (fileLastModifiedTime) for each entry in the index file
def getIndexFileMTimeMapping(keepFullPath=False):
	if not indexFileExists():
		return {}
	idxDict = {}
	fileContent = readFromFile(os.path.join(currDir, ".git", "index")).split("\n")[:-1]
	if keepFullPath:
		map(lambda x: idxDict.setdefault(x.split("\x00")[4], x.split("\x00")[5]), fileContent)
	else:
		map(lambda x: idxDict.setdefault(os.path.split(x.split("\x00")[4])[1], x.split("\x00")[5]), fileContent)
	return idxDict

#Generate a mapping from fileName(fullPath or relativePath depending on the flag passed) to (fileHash) for each entry in the index file
def getIndexFileHashMapping(keepFullPath=False):
	if not indexFileExists():
		return {}
	idxDict = {}
	fileContent = readFromFile(os.path.join(currDir, ".git", "index")).split("\n")[:-1]
	if keepFullPath:
		map(lambda x: idxDict.setdefault(x.split("\x00")[4], x.split("\x00")[2]), fileContent)
	else:
		map(lambda x: idxDict.setdefault(os.path.split(x.split("\x00")[4])[1], x.split("\x00")[2]), fileContent)
	return idxDict	

#Get the contents of the index file as list of strings where each item corresponds to a line in the index file
def getIndexFileList():
	if not indexFileExists():
		return []
	fileContent = readFromFile(os.path.join(currDir, ".git", "index")).split("\n")[:-1]
	return map(lambda x: x.split("\x00")[4], fileContent)

#Get the latest commit that was made against the current branch, i.e HEAD
def getLatestCommitForCurrentBranch():
	parentCommit = ""
	headContent = readFromFile(os.path.join(currDir, ".git", "HEAD"))
	if "ref:" not in headContent :
		return headContent
	filePath = os.path.join(currDir, ".git", headContent.split()[1])
	if os.path.isfile(filePath):
		parentCommit = readFromFile(filePath)
	return parentCommit

#Update the latest commit for the current branch to the commit provided as input
def updateCurrentBranchLatestCommit(commitHash):
	headFilePath = os.path.join(currDir, ".git", "HEAD")
	headContent = readFromFile(headFilePath)
	if "ref:" not in headContent:
		writeToFile(headFilePath, commitHash, "w")
		return
	currBranchFilePath = os.path.join(currDir, ".git", headContent.split()[1])
	writeToFile(currBranchFilePath, commitHash, "w")	

#Create all of the folders that are defined in folderLst as part of Git Init command
def createGitFolders(rootFolder):
	fullFolderPathLst = map(lambda x: os.path.join(currDir, rootFolder, x), folderLst)
	map(os.makedirs, fullFolderPathLst)

#Create all of the files that are defined in fileLstWithContent as part of Git Init command
def createGitFiles(rootFolder):
	fullFilePathLst = map(lambda x: [os.path.join(currDir, rootFolder, x[0]), x[1]], fileLstWithContent)	
	map(lambda x: writeToFile(x[0], x[1], 'w'), fullFilePathLst)

#Get the list of all the files from the working copy that contain user changes and exist within the provided directory
def getFilesToGitAdd(fullFileOrDirectory):
	filesToGitAdd = []
	if os.path.isdir(fullFileOrDirectory):
		filesToGitAdd = reduce(lambda y, acc: y + acc, map(lambda x: map(lambda z: os.path.join(x[0], z), x[2]) if ".git" not in x[0] else [], os.walk(fullFileOrDirectory)))
	else:
		filesToGitAdd = [fullFileOrDirectory]
	return filesToGitAdd

#Generate the compressed content and hash of the file specified by its relative path
def makeGitCompressedContentAndHashWithRelPath(filePath):
	fileContent = readFromFile(filePath)	
	finalContent = 'blob\x00' +  str(len(fileContent)) + '\x00' + fileContent
	relativePath, compressedContent, genHash = (os.path.relpath(filePath, currDir), zlib.compress(finalContent), sha1(finalContent).hexdigest())
	return (relativePath, compressedContent, genHash)

#Create the git blob object and corresponding directory(if required) using the files content and its hash
def writeGitBlobObjects(contentWithFilePathAndHash):
	objFilePath = contentWithFilePathAndHash[2][:2]
	objFileName = contentWithFilePathAndHash[2][2:]
	objFileContent = contentWithFilePathAndHash[1]
	blobObjectDir = os.path.join(currDir, ".git", "objects", objFilePath)
	checkAndCreateDir(blobObjectDir)
	writeToFile(os.path.join(blobObjectDir, objFileName), objFileContent, 'w')

#Update the index file with modifications for already added files reflecting the user changes
def updateGitIndexFileWithModifications(contentWithFilePathAndHash, permMode=100644, stage=0):
	prevIndexContent = []
	fileHash, fileRelativePath = contentWithFilePathAndHash[2], contentWithFilePathAndHash[0]
	fileLastModifiedTime = str(os.path.getmtime(os.path.join(currDir, fileRelativePath)))	
	if indexFileExists():
		prevIndexContent = readFromFile(os.path.join(currDir, ".git", "index")).split("\n")		
	contentToWrite = str(permMode) + "\x00blob\x00" + fileHash + "\x00" + str(stage) + "\x00" + fileRelativePath + "\x00" + fileLastModifiedTime
	if contentToWrite not in prevIndexContent:
		newIndexContent = map(lambda x: contentToWrite if fileRelativePath in x else x, prevIndexContent)		
		if newIndexContent == prevIndexContent:
			contentToWrite = "\n".join(prevIndexContent[:-1] + [contentToWrite + "\x00\n"])
		elif indexFileExists():
			contentToWrite = "\n".join(newIndexContent)		
		writeToFile(os.path.join(currDir, ".git", "index"), contentToWrite, "w")	

#Update the index file with deletions for already added files reflecting the files that the user deleted
def updateGitIndexFileWithDeletions(gitAddDirOrFile):	
	prevIndexContent = []
	if indexFileExists():
		prevIndexContent = readFromFile(os.path.join(currDir, ".git", "index")).split("\n")
	else:
		return False	
	checkIfIsUnder = lambda i: os.path.join(currDir, i).startswith(gitAddDirOrFile)
	updatedIndexContent = filter(lambda x: x == "" or not checkIfIsUnder(x.split("\x00")[4]) or (checkIfIsUnder(x.split("\x00")[4]) and os.path.isfile(os.path.join(currDir, x.split("\x00")[4]))), prevIndexContent)
	contentToWrite = "\n".join(updatedIndexContent)
	writeToFile(os.path.join(currDir, ".git", "index"), contentToWrite, "w")
	return True

#Generate the content of the Git tree object represented by the treeObj variable as string	
def getGitTreeObjectContent(treeObj):
	idxDict = getIndexFileHashMTimeMapping()		
	content = map(lambda x: "040000\x00tree\x00" + x.CurrDirHash + "\x00" + x.CurrDir, treeObj.DirTreeLst)	
	content = content + map(lambda x: "100644\x00blob\x00" + idxDict[x][0] + "\x00" + x, treeObj.FileHashMap)
	contentToWrite = "\n".join(content)	
	return contentToWrite

#Recursively traverse the working copy of the project and for each directory, generate a mapping of files and folders and create a tree object out of it.
#Generate the string contents of the tree object and write it to the file system under the git directory
def recursiveTraverseDirTree(fileLst, dirObj):	
	dirContents = getDirectoryContents(fileLst)
	fileLst,  folderLst = separateFilesAndFolder(dirContents)
	fileLstMap = {}
	map(lambda x: fileLstMap.setdefault(x, ""), fileLst)
	dirObj.FileHashMap = fileLstMap
	folderDict = groupSubDirectories(folderLst)	
	dirObj.DirTreeLst = map(lambda x: recursiveTraverseDirTree(folderDict[x], DirTree(x)), folderDict)
	contentToWrite = getGitTreeObjectContent(dirObj)
	if contentToWrite != "" and len(contentToWrite) > 2:
		dirObj.CurrDirHash = sha1(contentToWrite).hexdigest()		
		objPath = os.path.join(currDir, ".git", "objects", dirObj.CurrDirHash[:2])
		checkAndCreateDir(objPath)
		writeToFile(os.path.join(objPath, dirObj.CurrDirHash[2:]), zlib.compress(contentToWrite), "wb")
	return dirObj

#Generate the commit object and its contents using the root directory tree object and the user provided commit message
#The otherParent argument specfies if its a merge commit or a standard commit
def writeCommitObject(rootDirObj, commitMsg, otherParent=None):	
	contentToWrite = "tree\x00" + rootDirObj.CurrDirHash + "\n"
	parentCommit = getLatestCommitForCurrentBranch()
	if parentCommit != "":
		contentToWrite = contentToWrite + "parent\x00" + parentCommit + "\n"
	if otherParent is not None:
		contentToWrite = contentToWrite + "parent\x00" + otherParent + "\n"
	contentToWrite = contentToWrite + "'" + commitMsg + "'"
	commitObjectFile = sha1(contentToWrite).hexdigest()
	updateCurrentBranchLatestCommit(commitObjectFile)
	commitObjDir = os.path.join(currDir, ".git", "objects", commitObjectFile[:2])
	checkAndCreateDir(commitObjDir)
	writeToFile(os.path.join(commitObjDir, commitObjectFile[2:]), zlib.compress(contentToWrite), "wb")

#Perform the initial processing for making the git commit
def makeGitCommit(commitMsg, otherParent=None):	
	rootDirName = os.path.split(currDir)[1]
	rootDirObj = DirTree(rootDirName)
	fileLst = map(lambda x: os.path.join(rootDirName, x), getIndexFileList())
	rootDirObj = recursiveTraverseDirTree(fileLst, rootDirObj)
	writeCommitObject(rootDirObj, commitMsg, otherParent)

#Generate the hash of the file using sha1 for the file path provided
def generateFileHash(filePath):	
	fileContent = readFromFile(filePath)		
	newContent = 'blob\x00' +  str(len(fileContent)) + '\x00' + fileContent
	# print (filePath, fileContent, newContent)	
	return sha1(newContent).hexdigest()

#Recursively parse the contents of the tree objects and generate the corresponding tree objects
def parseFileAndMakeDirTreeObject(fileHash, objName=""):
	objName = objName if objName != "" else os.path.split(currDir)[1]
	filePath = os.path.join(currDir, ".git", "objects", fileHash[:2], fileHash[2:])
	fileContentLst = readFromFileAndDecompress(filePath).split("\n")	
	fileContentSpaceSep = map(lambda x: x.split("\x00"), fileContentLst)
	dirTreeObj = DirTree(objName)
	mapFunc = (lambda x: dirTreeObj.DirTreeLst.append(parseFileAndMakeDirTreeObject(x[2], x[3])) if (x[1] == "tree") else dirTreeObj.FileHashMap.setdefault(x[3], x[2]))
	map(mapFunc, fileContentSpaceSep)	
	return dirTreeObj
	
#Parse the contents of the commit object and generate the root tree object from it
def makeDirTreeObjectFromCommit(commitHash):	
	commitObjPath = os.path.join(currDir, ".git", "objects", commitHash[:2], commitHash[2:])
	uncompressedFileContent = readFromFileAndDecompress(commitObjPath)
	rootTreeHash = (uncompressedFileContent.split("\n")[0]).split("\x00")[1]
	rootTreeObj = parseFileAndMakeDirTreeObject(rootTreeHash)
	return rootTreeObj

#Recursively generate the mapping of files and their corresponding hash for a given tree object
def recursivelyGenerateFileHashMap(dirTreeObj, rootPath="", fullFilePath=False):
	tmpDict = {}
	if fullFilePath:
		updatedRootPath = os.path.join(rootPath, dirTreeObj.CurrDir)
		map(lambda x: tmpDict.setdefault(os.path.join(updatedRootPath,x), dirTreeObj.FileHashMap[x]) ,dirTreeObj.FileHashMap)
		map(lambda x: tmpDict.update(recursivelyGenerateFileHashMap(x, updatedRootPath, fullFilePath)), dirTreeObj.DirTreeLst)
		return tmpDict
	else:
		tmpDict.update(dirTreeObj.FileHashMap)
		map(lambda x: tmpDict.update(recursivelyGenerateFileHashMap(x)), dirTreeObj.DirTreeLst)
		return tmpDict	


#Returns the list of files that show differences in the index compared to their current state in local
def diffIndexAndLocal():
	fileAndMTimeDict = getIndexFileHashMTimeMapping(True)
	filterOutUnmodified = lambda x: not os.path.isfile(os.path.join(currDir, x)) or (fileAndMTimeDict[x][1] != str(os.path.getmtime(os.path.join(currDir, x))) or fileAndMTimeDict[x][0] != generateFileHash(os.path.join(currDir, x)))
	modifiedOrDeletedFilesLst = filter(filterOutUnmodified, fileAndMTimeDict)
	taggedLst = map (lambda x: x + ": Deleted" if not os.path.isfile(os.path.join(currDir, x)) else x + ": Modified", modifiedOrDeletedFilesLst)
	return taggedLst	

#Returns the list of files that show differences in the latest commit compared to their state in the index file
def diffLatestCommitAndIndex():	
	idxFileDict, rootDirName = {}, os.path.split(currDir)[1]
	relPathIdxFileDict = getIndexFileHashMapping(True)
	map(lambda x: idxFileDict.setdefault(os.path.join(rootDirName, x), relPathIdxFileDict[x]), relPathIdxFileDict)
	latestCommit = getLatestCommitForCurrentBranch()	
	if latestCommit == "":		
		return []
	rootTreeObj = makeDirTreeObjectFromCommit(latestCommit)
	cmtFileDict = recursivelyGenerateFileHashMap(rootTreeObj, "", True)	
	filterFunc = lambda x: ((x in cmtFileDict and cmtFileDict[x] != idxFileDict[x]) or (x not in cmtFileDict))
	modifiedFilesLst = filter(filterFunc, idxFileDict)
	modifiedFilesLst = modifiedFilesLst + filter(lambda x: x not in idxFileDict, cmtFileDict)
	checkFileAdded = lambda x: x in idxFileDict and x not in cmtFileDict
	checkFileDeleted = lambda x: x not in idxFileDict and x in cmtFileDict
	mapFunc = lambda x: x + ": Added" if checkFileAdded(x) else (x + ": Deleted" if checkFileDeleted(x) else x + ": Modified")
	taggedLst = map(mapFunc, modifiedFilesLst)
	return taggedLst	

#Returns the list of files that show differences in the latest commit as compared to thier current state in local
def diffLatestCommitAndLocal():
	idxFileDict = getIndexFileHashMapping(True)
	trackedFileLst = map(lambda x: os.path.join(currDir, x), idxFileDict)
	latestCommit = getLatestCommitForCurrentBranch()		
	if latestCommit == "":		
		return []
	rootTreeObj = makeDirTreeObjectFromCommit(latestCommit)
	cmtFileDict = recursivelyGenerateFileHashMap(rootTreeObj, os.path.split(currDir)[0], True)
	addedFileLst = map(lambda y: y + ": Added", filter(lambda x: x not in cmtFileDict, trackedFileLst))
	deletedFileLst = map(lambda y: y + ": Deleted", filter(lambda x: not os.path.isfile(x), cmtFileDict))
	deletedFileLst = deletedFileLst + map(lambda y: y + ": Deleted", filter(lambda x: not os.path.isfile(x) and (x + ": Deleted") not in deletedFileLst, trackedFileLst))		
	modifiedFilesLst = map(lambda y: y + ": Modified", filter(lambda x: x in cmtFileDict and (x + ": Deleted") not in deletedFileLst and generateFileHash(x) != cmtFileDict[x], trackedFileLst))	
	return addedFileLst + modifiedFilesLst + deletedFileLst

#Return the string content without extra '\x00' characters
def extractOriginalContent(objContent):	
	return objContent.split('\x00')[2]

#Parse and write the contents of the blob object to the specified file path
def writeBlobObjToFile(filePath, blobHash):
	objPath = os.path.join(currDir, ".git", "objects", blobHash[:2], blobHash[2:])
	objContent = readFromFileAndDecompress(objPath)
	origContent = extractOriginalContent(objContent)
	writeToFile(filePath, origContent, 'wb')

#Recursively traverse through the working copy applying the changes represented by the commit object
def recursivelyApplyCommitToWorkingCopy(treeObj, rootPath):
	if not os.path.isdir(rootPath):
		os.makedirs(rootPath)
	updatedRootPath = os.path.join(rootPath, treeObj.CurrDir)
	map(lambda x: writeBlobObjToFile(os.path.join(updatedRootPath, x), treeObj.FileHashMap[x]), treeObj.FileHashMap)
	map(lambda x: recursivelyApplyCommitToWorkingCopy(x, updatedRootPath), treeObj.DirTreeLst)

#Recursively traverse through the working copy deleting the changes represented by the commit object
def recursivelyDeleteCommitFromWorkingCopy(treeObj, rootPath):
	updatedRootPath = os.path.join(rootPath, treeObj.CurrDir)
	map(lambda x: deleteFileIfExists(os.path.join(updatedRootPath, x)), treeObj.FileHashMap)
	map(lambda x: recursivelyDeleteCommitFromWorkingCopy(x, updatedRootPath), treeObj.DirTreeLst)
	_, folders, files = os.walk(updatedRootPath).next()
	if not files and not folders:
		os.rmdir(updatedRootPath)

#Helper function for reflecting the changes represented by the commit object onto the index file
def applyCommitToIndexHelper(fileName, fileHash, permMode=100644, stage=0):
	fullFilePath = os.path.join(currDir, fileName)
	modifiedTime = str(os.path.getmtime(fullFilePath))	
	return str(permMode) + "\x00blob\x00" + fileHash + "\x00" + str(stage) + "\x00" + fileName + "\x00" + modifiedTime

#Generate the contents of the index file using the commit object provided as input
def recursivelyPrepareIndexFromCommit(treeObj, rootPath):
	resultLst = []
	updatedRootPath = os.path.join(rootPath, "" if treeObj.CurrDir == os.path.split(currDir)[1] else treeObj.CurrDir)
	resultLst = map(lambda x: applyCommitToIndexHelper(os.path.join(updatedRootPath, x), treeObj.FileHashMap[x]), treeObj.FileHashMap)	
	resultLst.extend(reduce(lambda acc, x: acc + recursivelyPrepareIndexFromCommit(x, updatedRootPath), treeObj.DirTreeLst, []))
	return resultLst

#Update the contents of the HEAD ref to point to the branch that is provided in the input
def updateHeadWithNewCurrentBranch(branchName):
	writeToFile(os.path.join(currDir, ".git", "HEAD"), "ref: refs\\heads\\" + branchName, 'w')

#Delete the changes represented by the old commit from the working copy and apply the changes represented by the new commit
def removeOldCommitAndApplyNewCommit(newCommit, oldCommit):
	newRootTreeObj, oldRootTreeObj = makeDirTreeObjectFromCommit(newCommit), makeDirTreeObjectFromCommit(oldCommit)
	recursivelyDeleteCommitFromWorkingCopy(oldRootTreeObj, os.path.split(currDir)[0])
	recursivelyApplyCommitToWorkingCopy(newRootTreeObj, os.path.split(currDir)[0])
	cmtFilesDict = recursivelyGenerateFileHashMap(newRootTreeObj, "", True)
	fileLst = getDirectoryContents(map(lambda x: x, cmtFilesDict))
	newIndexContent = "\n".join(recursivelyPrepareIndexFromCommit(newRootTreeObj, "")) + "\x00\n"
	writeToFile(os.path.join(currDir, ".git", "index"), newIndexContent, "w")

#Extract and return the parent/parents from the commit object provided as input
def extractParentCommit(commitContent):
	if commitContent.count("parent") == 1:
		fstParent = commitContent.split("\n")[1]				
		return (fstParent.split("\x00")[1], None)	
	elif commitContent.count("parent") > 1:
		fstParent, sndParent = commitContent.split("\n")[1], commitContent.split("\n")[2]
		return (fstParent.split("\x00")[1], sndParent.split("\x00")[1])
	else:
		return (None, None)				
		
#Get the list of all the ancestors of the current commit object by recursively travelling through the chain
def getCommitAncestory(commitHash, alreadyVisited=[]):	
	if not commitHash or commitHash in alreadyVisited:
		return None	
	alreadyVisited.append(commitHash)
	commitObjPath = os.path.join(currDir, ".git", "objects", commitHash[:2], commitHash[2:])
	rawCommitContent = readFromFileAndDecompress(commitObjPath)	
	# print "Commit Hash: ", commitHash
	# print "Commit Content: ", rawCommitContent
	parentCommit = extractParentCommit(rawCommitContent)			
	if parentCommit[1] is None:	
		return (commitHash, getCommitAncestory(parentCommit[0], alreadyVisited))
	else:
		return (commitHash, getCommitAncestory(parentCommit[0], alreadyVisited), getCommitAncestory(parentCommit[1], alreadyVisited))

#Flatten the commit ancestory that is a returned as a nested structure from getCommitAncestory function
def flattenCommitAncestory(commitAncestory):
	return sum( ([x] if not isinstance(x, tuple) else flattenCommitAncestory(x) for x in commitAncestory), [] )

#Generate the list of all conflicts and deletions represented by merging working copies obtained by the targetBranchIndex and currentBranchIndex
def generateResultIndexForMerge(targetBranchIdx, currBranchIdx, commonAncestorIdx):		
	resultDict, conflictsLst, deletedFilesLst = {}, [], []
	for key in commonAncestorIdx.keys():
		if key in targetBranchIdx and key not in currBranchIdx:
			if targetBranchIdx[key] != commonAncestorIdx[key]:
				conflictsLst.append(key)
			else:
				deletedFilesLst.append(key)
		elif key in currBranchIdx and key not in targetBranchIdx:
			if currBranchIdx[key] != commonAncestorIdx[key]:
				conflictsLst.append(key)
			else:
				deletedFilesLst.append(key)		
		elif key in targetBranchIdx and key in currBranchIdx:
			if targetBranchIdx[key] == currBranchIdx[key]:
				if targetBranchIdx[key] != commonAncestorIdx[key]:
					resultDict[key] = currBranchIdx[key]
			elif commonAncestorIdx[key] == targetBranchIdx[key]:
				resultDict[key] = currBranchIdx[key]
			elif commonAncestorIdx[key] == currBranchIdx[key]:
				resultDict[key] = targetBranchIdx[key]
			else:
				conflictsLst.append(key)
		else:
			deletedFilesLst.append(key)		

	for key in [x for x in currBranchIdx.keys() if x not in commonAncestorIdx]:
		if key not in targetBranchIdx or (targetBranchIdx[key] == currBranchIdx[key]):
			resultDict[key] = currBranchIdx[key]
		else:
			conflictsLst.append(key)

	for key in [x for x in targetBranchIdx.keys() if x not in commonAncestorIdx and x not in currBranchIdx]:
		resultLst[key] = targetBranchIdx[key]
		
	return ({"ResultIndex": resultDict, "ConflictsList": conflictsLst, "DeletedList" : deletedFilesLst}, conflictsLst != [])

# Git Functionality Methods

#The base function that is invoked when the user runs the git init command
#Before performing the init operation, we check if the user wants to create a bare or normal git repository and act accordingly
#The only action here is to create the files and folders which are part of every empty git directory
def init(isBare):
	if os.path.isdir(os.path.join(currDir, ".git")) or (isBare and os.path.isdir(os.path.join(currDir, "objects"))):
		return
	createGitFolders(".git" if not isBare else "")
	createGitFiles(".git" if not isBare else "")	

#The base function representing the git add command
#The user can provide the file or directory to add, or simply give '.' as the argument, in which case we add all the user files in the working copy to the index
#This function can also be invoked when applying a merge commit in which case the resultant working copy state is added to the index
#The sequence of actions here are:
#	1. Get the list of all files to git add within the provided directory
#	2. For each files, generate its hash and a compressed version of its content and create the index using these details
#	3. Generate blob objects for each of the files in the file list
#	4. If the index already contains files present in the list of files to git add, then update their entries in the index
#	5. If the index already contains fiels present in the list of files to git delete, then delete their entries from the index
def add(fileOrDirectory, addFromCommit=False, fullPathProvided=False):	
	if not fullPathProvided:
		fullFileOrDirectory = os.path.join(currDir, fileOrDirectory)
	else:
		fullFileOrDirectory = fileOrDirectory
	if not os.path.isfile(fullFileOrDirectory) and not os.path.isdir(fullFileOrDirectory):
		print "Invalid file(s). Cannot add to git"
		return
	filesToGitAdd = getFilesToGitAdd(fullFileOrDirectory)
	if addFromCommit and indexFileExists():
		idxFileContent = readFromFile(os.path.join(currDir, ".git", "index"))
		filesToGitAdd = filter(lambda x: x in idxFileContent, filesToGitAdd)
	contentAndHashWithRelPathLst = map(makeGitCompressedContentAndHashWithRelPath, filesToGitAdd)
	map(writeGitBlobObjects, contentAndHashWithRelPathLst)	
	map(updateGitIndexFileWithModifications, contentAndHashWithRelPathLst)
	updateGitIndexFileWithDeletions(fullFileOrDirectory)

#The base function representing the git cat-file command
#The sequence of actions here are:
#	1. Check if the input file provided is actually the index file in which case display its content
#	2. Otherwise for any other blob or tree object, get a hold of its file path in the git directory
#	3. Using the path generate the uncompressed content of the object and return the string content
def catFile(fileName):
	if fileName == "index":
		return readFromFile(os.path.join(currDir, ".git", "index"))		
	objFolderName = fileName[:2]
	dirToSearch = os.path.join(currDir, ".git", "objects",  objFolderName)
	objFileNameStart = fileName[2:]
	if len(fileName) <= 2 or not os.path.isdir(dirToSearch):
		return		
	(_, _, fileLst) = os.walk(dirToSearch).next()
	resultLst = filter(lambda x: x.startswith(objFileNameStart), fileLst)
	if resultLst:		
		return readFromFileAndDecompress(os.path.join(dirToSearch, resultLst[0]))

#The base function representing the git commit command
# The sequence of actions here are:
#	1. If the user wishes to add files before commiting then we do both add and commit operations
#	2. Otherwise invoke the core makeGitCommit function with the user provided commit message
def commit(addFirst, commitMsg="Default Commit Message"):
	if addFirst:
		add(currDir)
	makeGitCommit(commitMsg)

#The base function representing the git diff command
#The sequence of actions here are:
#	1. We check if the isCached flag is set by the user, if yes then the diff is performed between the index and the latest commit on the current branch
#	2. In case the isHead flag is set by the user, then the diff is performed between the latest commit on the current branch and the current state of the working copy
#	3. If the user has provided a branch name, then the diff is performed between the latest commit on the current branch and the latest commit on the target branch
#	4. If the user has provided a commit object hash (commit ID), then the diff is perfomed between the latest commit on the current branch and the provided commit object
#	5. If none of the above is true, then the diff is performed between the index and current state of the working copy
def diff(isCached, isHead, branchName="", commitID=""):
	diffFileLst = []
	if isCached:
		diffFileLst = diffLatestCommitAndIndex()
	elif isHead:
		diffFileLst = diffLatestCommitAndLocal()
	elif branchName != "":
		diffFileLst = diffCurrentAndTargetBranch(branchName)
	elif commitID != "":
		diffFileLst = diffCurrentBranchAndCommit(commitID)
	else:
		diffFileLst = diffIndexAndLocal()
	if not diffFileLst:
		return "There are no changes to display"
	return "\n".join(diffFileLst)

#The base function representing the git branch command
#The sequence of actions here are:
#	1. Get the full branch path from the provided branch name and check if such a branch already exists
#	2. If not then we check if the user has created atleast one branch. If not then we break, else continue
#	3. We get the current branch and its associated latest commit
#	4. We create the new branch with its full branch path and point it to the latest commit
def branch(branchName):
	branchPath = os.path.join(currDir, ".git", "refs", "heads", branchName)
	currBranchPath = os.path.join(currDir, ".git", readFromFile(os.path.join(currDir, ".git", "HEAD")).split()[1])
	if os.path.isfile(branchPath):
		return "Branch Already exists"
	elif not os.path.isfile(currBranchPath):	
		return "No branch currently checked out. Cannot create new branch"
	currBranchCommit = readFromFile(currBranchPath)
	writeToFile(branchPath, currBranchCommit, 'w')
	return "New branch " + branchName + " created successfully"

#The base function used for getting the current branch on a particular repo
#The sequence of actions here are:
#	1. Get the contents of the HEAD file which represent the current branch
#	2. Return the branch acquired in the previous step
def currentBranch():
	currBranchPath = readFromFile(os.path.join(currDir, ".git", "HEAD")).split()[1]
	return currBranchPath

#The base function for getting the latest commit for the branch provided as user input
#The sequence of actions here are:
#	1. If the user has not explicitly provided a branch name then we pull the latest commit for the current branch
#	2. If the user has provided a branch name, we use it to generate a full branch path and validate if its a correct branch
#	3. If yes, then we retrieve the latest commit pointed to by this branch and return to the user
def latestCommitByBranch(branchName=""):	
	if not branchName:
		return getLatestCommitForCurrentBranch()
	else:
		commitPath = os.path.join(currDir, ".git", "refs", "heads", branchName)
		if not os.path.isfile(commitPath):
			return "Invalid branch name"
		currBranchCommit = readFromFile(commitPath)
	return currBranchCommit

#The base function for checking out a git branch. This corresponds to the git checkout function.
#The sequence of actions here are:
#	1. Get the current branch that the user is working on by reading the contents of the HEAD file
#	2. Get the full path of the branch corresponding to the name provided in the input
#	3. If the branch aquired above is the same as the current branch, then no action needs to performed
#	4. If the branch provided by the user does not correspond to a valid branch path, then the checkout operation cannot be performed
#	5. Check if there are any pending changes in working copy, if yes then prevent the user from checking out a new branch since that can override these changes
#	6. Check if there are changes added for commit but not yet committed, if yes then prevent the user from checking out a new branch since that can override the index file
#	7. For both the current branch and the user provided branch, get the latest commit. Using these two commits invoke the removeOldCommitAndApplyNewCommit function
#	8. Once the commit for the user provided branch has been applied to the working copy, update the contents of the HEAD file to point to new checked out branch
def checkout(branchName):	
	branchPath = os.path.join(currDir, ".git", "refs", "heads", branchName)
	currBranchPath = os.path.join(currDir, ".git", readFromFile(os.path.join(currDir, ".git", "HEAD")).split()[1])
	if branchPath == currBranchPath:
		return "Already on branch " + branchName
	if not os.path.isfile(branchPath):
		return "The provided branch name does not exist. Checkout failed."
	if diffIndexAndLocal() != []:
		return "There are changes in working copy that are not yet added to git. Add and commit those changes before checking out a new branch"
	if diffLatestCommitAndIndex() != []:
		return "There are staged changes pending for commit. Please commit them before checking out a new branch"

	newCommit, oldCommit = readFromFile(branchPath), readFromFile(currBranchPath)
	removeOldCommitAndApplyNewCommit(newCommit, oldCommit)
	updateHeadWithNewCurrentBranch(branchName)
	return "Switched to branch " + branchName + " : Branch and working copy at commit " + newCommit

#The base function for the merge operation corresponding to the git merge command
#The sequence of actions here are:
#	1. Before doing anything for merge check if there are any pending changes on the current branch, either added (reflected in the index) but not committed or not added at all. If yes then abort the merge.
#	2. If not, then get the current branch and check if the provided branch is the same as the current branch. If yes then stop since the source and target branch for the merge are one and the same
#	3. If not, then get the latest commit corresponding to the current branch and the user provided branch. If either of the branches do not exist or have invalid commits, abort the merge
#	4. If not, then check if the two commits obtained are one and the same. If yes, then the two branches are at the same stage and no action needs to be performed for merge
#	5. If not, then generate the commit ancestory of the current branch by recursively traversing from the latest commit on that branch to the earliest commit
# 	6. From the commit ancestory obtained for the current branch, check if the provided branch is present somewhere in the chain. If yes then that means the provided branch is an ancestor of the current branch and hence has nothing to
#		give to the current branch. In essence, this means that the current branch is ahead of the provided branch and therefore no merge needs to be performed
#	7. If not, then we repeat the process of generating the ancestors but now we do it for the provided branch. We check if the current branch is present in the commit ancestory of the provided branch and if yes then the provided branch
#		is a descendant of the current branch. This means that there is a linear history between the two branches resulting in a straight forward merge. All that needs to be done is to make the current branch point to the latest commit
#		of the provided branch and the merge operation is completed.
#	8. If there is no direct relationship between the two branches then that means a commit intermittent in the ancestory chain relates the two branches. We find and extract that commit
#	9. With the three commits, current branch latest, provided branch latest and the common commit, we compare the changes according to the policy detailed in the blog post. If there are are any conflicts, we halt the merge operation 
#		and the user to resolve the conflicts before completing the merge. NOTE: Git actually creates temporary files like MERGE_HEAD, MERGE_MODE, MERGE_MSG etc when the merge halts due to conflicts. For simplicity purposes, those files
#		are not created in this implementation
#	10. If there are no conflicts, then we go ahead and perform a recursive merge taking changes from all the three aforementioned commits. It is done using the below steps:
#			a. Comparing the three commits provides us with the dictionary of files to add change, i.e mergeResultIdx and list of files to delete, i.e deletedFilesLst
#			b. For each entry in the deleted files list, we delete the corresponding files from the working copy
#			c. For each entry in the mergeResultIdx dictionary, we add or modify the files in the working copy
#			d. After all the deletes and updates, we use the git add command to add these files to the index
#			e. After adding to the index, we commit the changes by performing a merge commit
def merge(branchName):
	if diffIndexAndLocal() or diffLatestCommitAndIndex():
		return "There are unstaged or uncommited changes present in working copy. Merge aborted."
	currBranchPath = currentBranch()
	if branchName in currBranchPath:
		return "Same source and target branch provided for the merge. Aborting merge."
	targetBranchLatestCommit, currBranchLatestCommit = latestCommitByBranch(branchName), latestCommitByBranch()
	if "Invalid" in currBranchLatestCommit or "Invalid" in targetBranchLatestCommit:
		return "Invalid source or target branch. Aborting merge."
	if targetBranchLatestCommit == currBranchLatestCommit:
		return "Provided branch is on the same commit as the current branch. No merge required."
	currBranchCommitAncestory = getCommitAncestory(currBranchLatestCommit, [])
	currBranchCommitChain = flattenCommitAncestory(currBranchCommitAncestory)	
	checkIfAncestor = lambda x: x == targetBranchLatestCommit
	ancestorCommit = filter(checkIfAncestor, currBranchCommitChain)
	# Case: 1 [No Merge]
	if ancestorCommit:
		return "The provided branch's latest commit is an ancestor of the current branch's latest commit. No merge required"
	targetBranchCommitAncestory = getCommitAncestory(targetBranchLatestCommit, [])	
	targetBranchCommitChain = flattenCommitAncestory(targetBranchCommitAncestory)
	checkIfDescendant  = lambda x: x == currBranchLatestCommit
	descendantCommit = filter(checkIfDescendant, targetBranchCommitChain)
	# Case: 2 [Fast Forward Merge]
	if descendantCommit:
		returnString = "The provided branch's latest commit is a descendant of the current branch's latest commit. Performing Fast-Forward merge.\n"
		updateCurrentBranchLatestCommit(targetBranchLatestCommit)
		returnString += "Merge performed successfully."
		removeOldCommitAndApplyNewCommit(targetBranchLatestCommit, currBranchLatestCommit)		
		return returnString
	# Case: 3 [No Merge due to Conflicts]
	filterCommonAncestorCommit = lambda x: x in currBranchCommitChain
	commonAncestorCommit = filter(filterCommonAncestorCommit, targetBranchCommitChain)[0]
	generateIndexForCommit = lambda x: recursivelyGenerateFileHashMap(makeDirTreeObjectFromCommit(x), os.path.split(currDir)[0], True)	
	targetBranchIdx, currBranchIdx, commonAncestorIdx = map(generateIndexForCommit, [targetBranchLatestCommit, currBranchLatestCommit, commonAncestorCommit])
	returnValue, conflictExists = generateResultIndexForMerge(targetBranchIdx, currBranchIdx, commonAncestorIdx)
	mergeResultIdx, conflictsLst, deletedFilesLst = returnValue["ResultIndex"], returnValue["ConflictsList"], returnValue["DeletedList"]
	if conflictExists:
		returnString = "There exists conflict(s) between current branch and target branch. Following are the conflicting files: \n"
		for item in conflictsLst:
			returnString += item + "\n"
		return returnString
		
	# Case: 4 [Recursive Merge]	
	map(deleteFileIfExists, deletedFilesLst)
	filePathPrefix = os.path.join(currDir, ".git", "objects")
	writeMergeContentToWorkingCopy = lambda x: writeToFile(x, extractOriginalContent(readFromFileAndDecompress(os.path.join(filePathPrefix, mergeResultIdx[x][:2], mergeResultIdx[x][2:]))), 'w')
	map(writeMergeContentToWorkingCopy, mergeResultIdx)
	updateIndexWithMergeChanges = lambda x: add(x, False, True)
	map(updateIndexWithMergeChanges, mergeResultIdx)
	map(updateGitIndexFileWithDeletions, deletedFilesLst)
	mergeCommitMsg = "Merge commit from " + branchName + " to current branch"
	makeGitCommit(mergeCommitMsg, targetBranchLatestCommit)
	return "Merge from " + branchName + " to current branch completed successfully"

#The main git handler. There probably is a better approach to handling the command line switches for Git operations, but this implementation is for educational purposes and hence no attempts have to been made to rectify it further.
def mainGitHandler():
	argLst = sys.argv[1:]
	if len(argLst) == 0:
		return
	elif argLst[0] == "init" and len(argLst) == 2 and argLst[1] == "--bare":
#The user wishes to initialize the repository with Git and hence runs the git init command. We check for the presence of the 'bare' flag which would indicate the user's intention of creating a bare repository. If that is the case, no .git directory will be created and all of its contents will be added at the root level of the project.
		init(True)
		print "Bare Git repository initialized"
	elif argLst[0] == "init":
		init(False)
		print "Git repository initialized"
#The user wishes to add some files to git (add entries in index) by running the git add command. If the user provides '.' instead of the file or directory name, it means we should add all files in the project directory.
	elif argLst[0] == "add" and len(argLst) <= 1:
		print "Please provide the file/directory to add to git"
	elif argLst[0] == "add":
		add(argLst[1]) if argLst[1] != "." else add(currDir)
		print "File(s) staged for commit"
#For blob objects like commit and tree objects, the user can use the git cat-file command providing the hash of the file that the user wishes to view in plain text. This command can also be used to view contents of index file.
	elif argLst[0] == "cat-file" and len(argLst) <= 1:
		print "Please provide the git blob object to read"
	elif argLst[0] == "cat-file" and len(argLst) == 3 and argLst[2] == "-p":
		val = catFile(argLst[1])
		print val[val.index('\x00')+1 : ]
	elif argLst[0] == "cat-file":
		print catFile(argLst[1])
#The user wishes to commit his/her changes to Git. Before completing the commit command, we perform a few preliminary checks:
#			1. If the user wishes to commit all changes (added and unadded) then we check if there is any difference between index and the local working copy. If no, then we stop the commit operation saying no files to commit.
#			2. If the user wishes to commit only added files (default) then we check if there is any difference between the index and the latest commit. If no, then we stop the commit operation saying no files to commit.
#The user can also use the -m flag to provide the message for the commit.
	elif argLst[0] == "commit" and len(argLst) <= 1:
		ans = raw_input("You are about to perform a commit, please make sure all your working files are added in git. Continue (y/n): ")
		if ans.lower() == "y":
			if not diffLatestCommitAndIndex() and getLatestCommitForCurrentBranch() != "":
				print "There are no file(s) to commit"
				return
			commit(False)
		print "File(s) committed successfully"
	elif argLst[0] == "commit" and argLst[1] == '-m':
		if not diffLatestCommitAndIndex() and getLatestCommitForCurrentBranch() != "":
			print "There are no file(s) to commit"
			return
		commit(False, argLst[2])	
		print "File(s) committed successfully"
	elif argLst[0] == "commit" and argLst[1] == '-a':
		if not diffIndexAndLocal() and getLatestCommitForCurrentBranch() != "":
			print "There are no file(s) to commit"
			return		
		commit(True)	
		print "File(s) committed successfully"
#The user wishes to view the difference of state between either:
#			1. Working copy and index
#			2. Working copy and latest commit
#			3. Index and latest commit					
	elif argLst[0] == "diff" and len(argLst) <= 1:
		print diff(False, False)
		print "Diff performed successfully"
	elif argLst[0] == "diff" and argLst[1] == "--cached":
		print diff(True, False)
		print "Diff performed successfully"
	elif argLst[0] == "diff" and argLst[1] == "HEAD":
		print diff(False, True)
		print "Diff performed successfully"
	elif argLst[0] == "diff" and argLst[1] == "-b":
		print diff(False, False, branchName=argLst[2])
		print "Diff performed successfully"
	elif argLst[0] == "diff" and argLst[1] == "-c":
		print diff(False, False, commitID=argLst[2])
		print "Diff performed successfully"
#The user wishes to create a new branch using the branch command
	elif argLst[0] == "branch" and len(argLst) == 2:
		print branch(argLst[1])
#The user wishes to checkout a particular branch from the list of already created branches
	elif argLst[0] == "checkout" and len(argLst) == 2:
		print checkout(argLst[1])
#The user wishes to query which is the current branch that is checked out in the project		
	elif argLst[0] == "current_branch":
		print currentBranch()
#The user wishes to view the hash of the latest commit for a particular branch		
	elif argLst[0] == "latest_commit" and len(argLst) == 3 and argLst[1] == "branch_name":
		print latestCommitByBranch(argLst[2])
	elif argLst[0] == "latest_commit":
		print latestCommitByBranch()
#The user wishes to merge the target branch into the source or current branch		
	elif argLst[0] == "merge" and len(argLst) == 3 and argLst[1] == "branch_name":
		print merge(argLst[2])
	elif argLst[0] == "merge":
		print "The merge command requires the branch name to merge to the current branch"

#The main Git handler method, which routes all of the git commands to the above module
if __name__ == "__main__":
	mainGitHandler()		
