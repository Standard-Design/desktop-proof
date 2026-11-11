#target indesign
// Standalone command: no listeners and no changes to the equation editor.
(function () {
    var home = File($.fileName).parent;
    $.evalFile(File(home.fsName + '/desktop_proof.jsxinc'));
    DesktopProof.run(home);
}());
