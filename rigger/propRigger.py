from maya import cmds as cmd
from filesystem import *
import api, exportManagerCore, skinCluster, modelCompiler

mel = api.mel
melecho = api.melecho


kFWD_AXIS = 'x'
exportManager = exportManagerCore.ExportManager()

def rigProp():
	curFile = cmd.file(q=True, sn=True)
	if curFile is None:
		api.melError('please save your scene first')

	curFile = Path(curFile)
	propName = curFile.name()

	#strip any model identifier
	propName = propName.replace('_reference', '').replace('_model', '')

	#make sure all items in the export set are parented under the info node - this makes exporting animation for the prop easier
	asset = modelCompiler.findComponent( 'model' )
	for o in asset.getObjs():
		try:
			cmd.parent(o, exportManager.node)
		except Exception, e:
			print 'failed to parent', e
			continue

	#save and create a new file
	cmd.file(save=True, f=True)
	cmd.file(new=True, f=True)

	cmd.file(str(curFile), reference=True, ns='model')

	#get teh prop scale
	scale = 1

	#create the rig world
	world, parts, masterqss, qss, infoNode = mel.zooCSTBuildWorld(propName, '-scale %s' % scale)

	#get all the joints in the prop
	joints = cmd.ls(type='joint')
	jointControls = {}

	for j in joints:
		jScale = skinCluster.getJointScale(j)
		ctrl = mel.zooBuildControl('%s_control' % j, '-axis %s -scale %s -type sphere -colour orange 0.7 -orient 1 -place %s -align %s -constrain 1 -parent %s' % (kFWD_AXIS, jScale, j, j, world))
		cmd.sets(ctrl, add=qss)
		ctrlSpace = cmd.listRelatives(ctrl, p=True, pa=True)[0]

		jointControls[j] = ctrlSpace

	#now parent the controls to mirror the heirarchy of the joints they control
	for j, ctrl in jointControls.iteritems():
		#does teh joint have a parent?  if so, parent the control to control controlling the joint's parent.  make sense?  8-o
		try:
			jParent = cmd.listRelatives(j, p=True, pa=True)[0]
		except TypeError: continue

		try:
			cmd.parent(ctrl, jointControls[jParent])
		except KeyError: pass

	rigFile = curFile.up() / ('%s_rig.ma' % propName)
	cmd.file(rename=str(rigFile))
	cmd.file(save=True, f=True)

	rigFileP4 = rigFile.asP4()
	rigFileP4.add()
	rigFileP4.setChange( curFile.asP4().getChange() )
	print 'change is:', rigFileP4.getChange(), curFile.asP4().getChange()

	api.doConfirm(t="rig created!", m="a rig has been created for this prop!\n\nfeel free to add/modify this rig as you see fit.  If the controls are too\nbig/small, select the verts for the controls and scale them accordingly", b=('THANKS!',))


#end