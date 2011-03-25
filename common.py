
from maya.OpenMaya import MGlobal
from exceptionHandlers import generateTraceableStrFactory


generateInfoStr, printInfoStr = generateTraceableStrFactory( '*** INFO ***', MGlobal.displayInfo )
generateWarningStr, printWarningStr = generateTraceableStrFactory( '', MGlobal.displayWarning )
generateErrorStr, printErrorStr = generateTraceableStrFactory( '', MGlobal.displayError )


#end
