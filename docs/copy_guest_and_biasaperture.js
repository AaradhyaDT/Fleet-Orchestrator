/**
 * Google Apps Script: Copy Guest Lecture, BiasAperture TA Review, and Proposal Defence
 * 
 * Target Google Drive Root Folder:
 * https://drive.google.com/drive/u/0/folders/1PFGKaftNDxqUvmUvQWe-oGlJ8yvrBU9C ("Recordings")
 */

var ROOT_FOLDER_ID = "1PFGKaftNDxqUvmUvQWe-oGlJ8yvrBU9C";

function copyTargetSpecialSessions() {
  var rootFolder = DriveApp.getFolderById(ROOT_FOLDER_ID);
  
  var targets = [
    {
      id: "1PuSz2wWj0ZLtc1_L1Np1cy60mCxwXrC3",
      name: "2026-09-19 - Guest Lecture: Agentic AI in Industry (Ayush Kumar Shah) - Recording.mp4",
      subfolder_path: ["02_Guest_Lectures", "2026-09-19 - Agentic AI in Industry (Ayush Kumar Shah)"]
    },
    {
      id: "1KAvtcVHBzl0gkRhQD7wfJFtr5CgUGHVs",
      name: "2026-10-14 - TA Session - BiasAperture - Recording.mp4",
      subfolder_path: ["04_TA_Sessions", "Capstone - BiasAperture"]
    },
    {
      id: "1_lJZ61dpNjwqJaHAJvgY5f_4Ld0QkXi1",
      name: "2026-09-07 - AIF - Proposal Defence (Aaradhya Dev Tamrakar) - Recording.mp4",
      subfolder_path: ["04_TA_Sessions", "Capstone - BiasAperture"]
    }
  ];

  Logger.log("Starting copy for " + targets.length + " target recordings...");

  for (var i = 0; i < targets.length; i++) {
    var item = targets[i];
    var targetFolder = resolvePath(rootFolder, item.subfolder_path);
    
    var existing = targetFolder.getFilesByName(item.name);
    if (existing.hasNext()) {
      Logger.log("[" + (i + 1) + "/" + targets.length + "] Already exists, skipping: " + item.name);
      continue;
    }
    
    try {
      var sourceFile = DriveApp.getFileById(item.id);
      sourceFile.makeCopy(item.name, targetFolder);
      Logger.log("[" + (i + 1) + "/" + targets.length + "] SUCCESS: Copied " + item.name + " -> " + item.subfolder_path.join("/"));
      Utilities.sleep(300);
    } catch (e) {
      Logger.log("[" + (i + 1) + "/" + targets.length + "] ERROR copying " + item.name + " (" + item.id + "): " + e.message);
    }
  }

  Logger.log("\n=== COMPLETED ALL COPIES ===");
}

function resolvePath(rootFolder, pathParts) {
  var current = rootFolder;
  for (var i = 0; i < pathParts.length; i++) {
    var name = pathParts[i];
    var subs = current.getFoldersByName(name);
    if (subs.hasNext()) {
      current = subs.next();
    } else {
      current = current.createFolder(name);
      Logger.log("Created folder: " + name);
    }
  }
  return current;
}
