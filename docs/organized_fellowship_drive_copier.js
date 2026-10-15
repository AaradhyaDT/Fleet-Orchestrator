/**
 * Google Apps Script: Hierarchical AI Fellowship 2026 Recordings Organizer
 * 
 * Target Google Drive Root Folder:
 * https://drive.google.com/drive/u/0/folders/1PFGKaftNDxqUvmUvQWe-oGlJ8yvrBU9C ("Recordings")
 *
 * Folder Taxonomy:
 * 📁 Recordings/
 *   ├── 📁 01_Weekly_Lectures/ (Week 01 to Week 18 subfolders)
 *   ├── 📁 02_Guest_Lectures/ (Meta Industry Guest Lecture)
 *   ├── 📁 03_Office_Hours_and_KSS/ (Organized by date and topic)
 *   └── 📁 04_TA_Sessions/ (Bimarsha Khanal, Raj Kumar, Rakshya, Pawan, Shreejan, Capstone)
 */

var ROOT_FOLDER_ID = "1PFGKaftNDxqUvmUvQWe-oGlJ8yvrBU9C";

// ==========================================
// PRIMARY RUNNERS (Select one in the toolbar dropdown & click Run)
// ==========================================

/**
 * 1. [DEFAULT] Copies all Weekly Lectures (Weeks 1 to 18)
 * Fastest run (~1.5 min)
 */
function copyWeeklyLectures() {
  var items = ALL_ITEMS.filter(function(item) {
    return item.category === "lectures";
  });
  runCopyProcess(items, "Weekly Lectures");
}

/**
 * 2. Copies Meta Guest Lecture & all Office Hours / KSS (~1 min)
 */
function copyGuestLecturesAndOfficeHours() {
  var items = ALL_ITEMS.filter(function(item) {
    return item.category === "guest" || item.category === "office_hours";
  });
  runCopyProcess(items, "Guest Lectures & Office Hours");
}

/**
 * 3. Copies all TA Sessions (Bimarsha, Raj Kumar, Rakshya, Pawan, Shreejan, Capstone)
 */
function copyTASessions() {
  var items = ALL_ITEMS.filter(function(item) {
    return item.category === "ta";
  });
  runCopyProcess(items, "TA Sessions");
}

/**
 * 4. Master Runner: Copies everything in sequence with safety watchdogs
 */
function copyAllRecordings() {
  runCopyProcess(ALL_ITEMS, "All Fellowship Media");
}

// ==========================================
// CORE COPY RUNNER & HELPERS
// ==========================================

/**
 * Helper to get or create nested subfolders inside a parent folder
 */
function resolveSubfolderPath(rootFolder, pathParts) {
  if (!rootFolder) {
    rootFolder = DriveApp.getFolderById(ROOT_FOLDER_ID);
  }
  if (!pathParts || !Array.isArray(pathParts) || pathParts.length === 0) {
    return rootFolder;
  }
  var currentFolder = rootFolder;
  for (var i = 0; i < pathParts.length; i++) {
    var partName = pathParts[i];
    var subfolders = currentFolder.getFoldersByName(partName);
    if (subfolders.hasNext()) {
      currentFolder = subfolders.next();
    } else {
      currentFolder = currentFolder.createFolder(partName);
      Logger.log("Created folder: " + partName);
    }
  }
  return currentFolder;
}

/**
 * Core copy runner with deduplication and safe time watchdog
 */
function runCopyProcess(itemsToProcess, processName) {
  var startTime = new Date().getTime();
  var MAX_EXECUTION_TIME_MS = 300000; // 5 minutes safety limit (Google limit is 6 min)

  Logger.log(">>> Starting [" + processName + "] for " + itemsToProcess.length + " items...");

  var rootFolder = DriveApp.getFolderById(ROOT_FOLDER_ID);
  var folderCache = {};

  var successCount = 0;
  var skipCount = 0;
  var errorCount = 0;

  for (var i = 0; i < itemsToProcess.length; i++) {
    // Check watchdog timer
    if (new Date().getTime() - startTime > MAX_EXECUTION_TIME_MS) {
      Logger.log("WARNING: Approaching execution time limit (5 mins). Safely pausing.");
      Logger.log("Run the function again to resume - all completed files are preserved.");
      break;
    }

    var item = itemsToProcess[i];
    var pathKey = item.subfolder_path.join("/");

    // Cache folders to avoid redundant Drive queries
    if (!folderCache[pathKey]) {
      folderCache[pathKey] = resolveSubfolderPath(rootFolder, item.subfolder_path);
    }
    var targetSubfolder = folderCache[pathKey];

    // Check if file already exists in this folder
    var existingFiles = targetSubfolder.getFilesByName(item.name);
    if (existingFiles.hasNext()) {
      Logger.log("[" + (i + 1) + "/" + itemsToProcess.length + "] Already exists, skipping: " + item.name);
      skipCount++;
      continue;
    }

    try {
      var sourceFile = DriveApp.getFileById(item.id);
      sourceFile.makeCopy(item.name, targetSubfolder);
      Logger.log("[" + (i + 1) + "/" + itemsToProcess.length + "] Copied: " + item.name + " -> " + pathKey);
      successCount++;
      Utilities.sleep(350); // polite pause between copy operations
    } catch (e) {
      Logger.log("[" + (i + 1) + "/" + itemsToProcess.length + "] ERROR copying " + item.name + " (" + item.id + "): " + e.message);
      errorCount++;
    }
  }

  Logger.log("=== COMPLETED [" + processName + "] ===");
  Logger.log("Successfully copied: " + successCount);
  Logger.log("Skipped (already exists): " + skipCount);
  Logger.log("Errors: " + errorCount);
}

// Master dataset of items to copy
var ALL_ITEMS = [
  {
    "id": "1bFho6UTP7zvY2Q7uh5wYaeZ4pd9_kFc9",
    "name": "2026-05-03 - Week 1 _ Data Wrangling - Chat.txt",
    "type": "chat",
    "date": "2026-05-03",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 01 - Data Wrangling"
    ],
    "summary": "Week 1 : Data Wrangling"
  },
  {
    "id": "1Lacuvn9XCxFMvVPwV3hE3Pl4azOXfMRL",
    "name": "2026-05-03 - Week 1 _ Data Wrangling - Recording.mp4",
    "type": "video",
    "date": "2026-05-03",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 01 - Data Wrangling"
    ],
    "summary": "Week 1 : Data Wrangling"
  },
  {
    "id": "1PAOYdOZOGJkBb3ftHwNRlm0UY4ZW6cIm",
    "name": "2026-05-10 - Week 2_ Agentic Software Development - Chat.txt",
    "type": "chat",
    "date": "2026-05-10",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 02 - Agentic Software Development"
    ],
    "summary": "Week 2: Agentic Software Development"
  },
  {
    "id": "17V2kGNbowAdEYu1Je6UOwwlE7fZyTyfZ",
    "name": "2026-05-10 - Week 2_ Agentic Software Development - Recording.mp4",
    "type": "video",
    "date": "2026-05-10",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 02 - Agentic Software Development"
    ],
    "summary": "Week 2: Agentic Software Development"
  },
  {
    "id": "1lnOKww7e50QKd3Ur06KXYk4cPC0iUSWm",
    "name": "2026-05-17 - Week 3_ Generative AI, Prompt Engineering, Agentic AI Overview - Chat.txt",
    "type": "chat",
    "date": "2026-05-17",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 03 - Generative AI, Prompt Engineering, Agentic AI Overview"
    ],
    "summary": "Week 3: Generative AI, Prompt Engineering, Agentic AI Overview"
  },
  {
    "id": "1U4fI4OgnMcd8oloW2GCU0DVS-0XO6kjh",
    "name": "2026-05-17 - Week 3_ Generative AI, Prompt Engineering, Agentic AI Overview - Recording.mp4",
    "type": "video",
    "date": "2026-05-17",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 03 - Generative AI, Prompt Engineering, Agentic AI Overview"
    ],
    "summary": "Week 3: Generative AI, Prompt Engineering, Agentic AI Overview"
  },
  {
    "id": "1leXlJbrqxTrvzk_beyv--QKUCQd3M7R7",
    "name": "2026-05-24 - Week 4_ Linear Models - Chat.txt",
    "type": "chat",
    "date": "2026-05-24",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 04 - Linear Models"
    ],
    "summary": "Week 4: Linear Models"
  },
  {
    "id": "1QaE5JROBtKjh1YeAFuqqboDLQqEhWX-m",
    "name": "2026-05-24 - Week 4_ Linear Models - Recording.mp4",
    "type": "video",
    "date": "2026-05-24",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 04 - Linear Models"
    ],
    "summary": "Week 4: Linear Models"
  },
  {
    "id": "1PLmqSvBh2xD0w_09fAxVsv-BFOrzZkQ-",
    "name": "2026-05-25 - Week 4_ Linear Models (Rescheduled) - Chat.txt",
    "type": "chat",
    "date": "2026-05-25",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 04 - Linear Models (Rescheduled)"
    ],
    "summary": "Week 4: Linear Models (Rescheduled)"
  },
  {
    "id": "1z93ntSHWeK8z5D4pIfVBki4CzF_YGKQ7",
    "name": "2026-05-25 - Week 4_ Linear Models (Rescheduled) - Recording.mp4",
    "type": "video",
    "date": "2026-05-25",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 04 - Linear Models (Rescheduled)"
    ],
    "summary": "Week 4: Linear Models (Rescheduled)"
  },
  {
    "id": "1G5Au7aUdssEJ0XHh3nN_JySuFZzqsMwi",
    "name": "2026-05-31 - Week 5_ Trees and Ensemble Method - Chat.txt",
    "type": "chat",
    "date": "2026-05-31",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 05 - Trees and Ensemble Method"
    ],
    "summary": "Week 5: Trees and Ensemble Method"
  },
  {
    "id": "1ZPzjrgVk4mv6PWDEPWA3KEZddW1lPxw_",
    "name": "2026-05-31 - Week 5_ Trees and Ensemble Method - Recording.mp4",
    "type": "video",
    "date": "2026-05-31",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 05 - Trees and Ensemble Method"
    ],
    "summary": "Week 5: Trees and Ensemble Method"
  },
  {
    "id": "1le-BRbscIi2b3YUzULXnTl16OI-6FhFZ",
    "name": "2026-06-07 - Week 6_ Probabilistic Models - Chat.txt",
    "type": "chat",
    "date": "2026-06-07",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 06 - Probabilistic Models"
    ],
    "summary": "Week 6: Probabilistic Models"
  },
  {
    "id": "1shmztjOvaFYviSCz380LXdCSpbOOSKZk",
    "name": "2026-06-07 - Week 6_ Probabilistic Models - Recording.mp4",
    "type": "video",
    "date": "2026-06-07",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 06 - Probabilistic Models"
    ],
    "summary": "Week 6: Probabilistic Models"
  },
  {
    "id": "1Yg2rmilgb99iH8aPMIKhNLvEaY29_l73",
    "name": "2026-06-21 - Week 7 _ Clustering - Chat.txt",
    "type": "chat",
    "date": "2026-06-21",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 07 - Clustering"
    ],
    "summary": "Week 7 : Clustering"
  },
  {
    "id": "1xYt-cvPOciP3dOWKwuSq7fGs03I2mgBL",
    "name": "2026-06-21 - Week 7 _ Clustering - Recording.mp4",
    "type": "video",
    "date": "2026-06-21",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 07 - Clustering"
    ],
    "summary": "Week 7 : Clustering"
  },
  {
    "id": "1lr3YvZEhdwZCXuHquuIzBhlC1Z0O1smj",
    "name": "2026-06-28 - Week 8 _ Forecasting - Chat.txt",
    "type": "chat",
    "date": "2026-06-28",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 08 - Forecasting"
    ],
    "summary": "Week 8 : Forecasting"
  },
  {
    "id": "19lDCFpN2xORbdxOeKaY-jXaESXReTOEn",
    "name": "2026-06-28 - Week 8 _ Forecasting - Recording.mp4",
    "type": "video",
    "date": "2026-06-28",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 08 - Forecasting"
    ],
    "summary": "Week 8 : Forecasting"
  },
  {
    "id": "1pzHzkV8VCKY6d0acceJhpcJLLSCoJYwt",
    "name": "2026-07-12 - Week 10 _ Handling Image Data - Chat.txt",
    "type": "chat",
    "date": "2026-07-12",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 10 - Handling Image Data"
    ],
    "summary": "Week 10 : Handling Image Data"
  },
  {
    "id": "1zHbp2-7HZuM4TDLMi1VQRvcV_qJ1Klp0",
    "name": "2026-07-12 - Week 10 _ Handling Image Data - Recording.mp4",
    "type": "video",
    "date": "2026-07-12",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 10 - Handling Image Data"
    ],
    "summary": "Week 10 : Handling Image Data"
  },
  {
    "id": "1zOa8Xdovy8xSkqatT-vMhjA9jvthkDec",
    "name": "2026-07-19 - Week 11_ Computer Vision - Chat.txt",
    "type": "chat",
    "date": "2026-07-19",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 11 - Computer Vision"
    ],
    "summary": "Week 11: Computer Vision"
  },
  {
    "id": "1aCXq6l0zdH6JOuW_tbdeF7wyDLbYKDq2",
    "name": "2026-07-19 - Week 11_ Computer Vision - Recording.mp4",
    "type": "video",
    "date": "2026-07-19",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 11 - Computer Vision"
    ],
    "summary": "Week 11: Computer Vision"
  },
  {
    "id": "1lL7j3wsbNSXgLSEjy57kN_kwV_wAEo9D",
    "name": "2026-07-26 - Week 12 _ Natural Language Processing - Chat.txt",
    "type": "chat",
    "date": "2026-07-26",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 12 - Natural Language Processing"
    ],
    "summary": "Week 12 : Natural Language Processing"
  },
  {
    "id": "16zA2Ko6znIvvjpzEiREmdQQQbzyy1s6W",
    "name": "2026-07-26 - Week 12 _ Natural Language Processing - Recording.mp4",
    "type": "video",
    "date": "2026-07-26",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 12 - Natural Language Processing"
    ],
    "summary": "Week 12 : Natural Language Processing"
  },
  {
    "id": "10RgT_wi5JmW4L2ZKX33dAVwTQbes3OaE",
    "name": "2026-08-02 - Week 13_ Sequence Learning - Chat.txt",
    "type": "chat",
    "date": "2026-08-02",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 13 - Sequence Learning"
    ],
    "summary": "Week 13: Sequence Learning"
  },
  {
    "id": "12vKi0LQaLjVgaWsC-GaZrkhKqwMVSRxk",
    "name": "2026-08-02 - Week 13_ Sequence Learning - Recording.mp4",
    "type": "video",
    "date": "2026-08-02",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 13 - Sequence Learning"
    ],
    "summary": "Week 13: Sequence Learning"
  },
  {
    "id": "1OR_LzraqACDQsMtcm018HUO7qlPzq2lI",
    "name": "2026-08-09 - Week 14_ Transformers, LLMs and Foundation Models - Chat.txt",
    "type": "chat",
    "date": "2026-08-09",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 14 - Transformers, LLMs and Foundation Models"
    ],
    "summary": "Week 14: Transformers, LLMs and Foundation Models"
  },
  {
    "id": "10b8iMqPVYt72W3afU1TRIXX53h2riUSu",
    "name": "2026-08-09 - Week 14_ Transformers, LLMs and Foundation Models - Recording.mp4",
    "type": "video",
    "date": "2026-08-09",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 14 - Transformers, LLMs and Foundation Models"
    ],
    "summary": "Week 14: Transformers, LLMs and Foundation Models"
  },
  {
    "id": "1E5LoaDhJhSvca0m2Vzm1ib7Nv3if-X1A",
    "name": "2026-08-30 - Week 15_ Applied Systems - Chat.txt",
    "type": "chat",
    "date": "2026-08-30",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 15 - Applied Systems"
    ],
    "summary": "Week 15: Applied Systems"
  },
  {
    "id": "12Ohsw71eWUFTt5ngQY-fuMR4I2QiMAfH",
    "name": "2026-08-30 - Week 15_ Applied Systems - Recording.mp4",
    "type": "video",
    "date": "2026-08-30",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 15 - Applied Systems"
    ],
    "summary": "Week 15: Applied Systems"
  },
  {
    "id": "1VDFtg_s_8pW3zvF_fu7U_UvzPX7ZKhi7",
    "name": "2026-09-06 - Week 16_ Agentic AI - Chat.txt",
    "type": "chat",
    "date": "2026-09-06",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 16 - Agentic AI"
    ],
    "summary": "Week 16: Agentic AI"
  },
  {
    "id": "1K2HtaX423AnO2SHZNphVrKCS-XXaOxB1",
    "name": "2026-09-06 - Week 16_ Agentic AI - Recording.mp4",
    "type": "video",
    "date": "2026-09-06",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 16 - Agentic AI"
    ],
    "summary": "Week 16: Agentic AI"
  },
  {
    "id": "1LaKaY_axemL2x1Lqr-3yBVMMuLByovhK",
    "name": "2026-09-06 - Week 16_ Agentic AI - Recording.mp4",
    "type": "video",
    "date": "2026-09-06",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 16 - Agentic AI"
    ],
    "summary": "Week 16: Agentic AI"
  },
  {
    "id": "1dK938ScvT-YdesGRonAdTklBdceORSK6",
    "name": "2026-09-13 - Week 17_  AI Systems & MLOps - Chat.txt",
    "type": "chat",
    "date": "2026-09-13",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 17 - AI Systems & MLOps"
    ],
    "summary": "Week 17:  AI Systems & MLOps"
  },
  {
    "id": "185naIPDIGUgWcDIlb7QcVHvYYwzSs_ZN",
    "name": "2026-09-13 - Week 17_  AI Systems & MLOps - Recording.mp4",
    "type": "video",
    "date": "2026-09-13",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 17 - AI Systems & MLOps"
    ],
    "summary": "Week 17:  AI Systems & MLOps"
  },
  {
    "id": "1w3bE9ifxqiRT6-oSWucEDN_rY1zkSXUZ",
    "name": "2026-10-11 - Week 18_ Responsible and TrusthWorthy AI - Chat.txt",
    "type": "chat",
    "date": "2026-10-11",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 18 - Responsible and TrusthWorthy AI"
    ],
    "summary": "Week 18: Responsible and TrusthWorthy AI"
  },
  {
    "id": "1GoTgtFMNv3GNMpU_jclc97PTTE1x5GXK",
    "name": "2026-10-11 - Week 18_ Responsible and TrusthWorthy AI - Recording.mp4",
    "type": "video",
    "date": "2026-10-11",
    "category": "lectures",
    "subfolder_path": [
      "01_Weekly_Lectures",
      "Week 18 - Responsible and TrusthWorthy AI"
    ],
    "summary": "Week 18: Responsible and TrusthWorthy AI"
  },
  {
    "id": "1xr6qJWYsJMJLPSgC9_ICPjmZfdEgBDhY",
    "name": "2026-09-19 - Guest Lecture_ Agentic AI in Industry with Meta's Ayush Kumar Shah - Chat.txt",
    "type": "chat",
    "date": "2026-09-19",
    "category": "guest",
    "subfolder_path": [
      "02_Guest_Lectures",
      "2026-09-19 - Agentic AI in Industry (Ayush Kumar Shah)"
    ],
    "summary": "Guest Lecture: Agentic AI in Industry with Meta's Ayush Kumar Shah"
  },
  {
    "id": "1PuSz2wWj0ZLtc1_L1Np1cy60mCxwXrC3",
    "name": "2026-09-19 - Guest Lecture_ Agentic AI in Industry with Meta's Ayush Kumar Shah - Recording.mp4",
    "type": "video",
    "date": "2026-09-19",
    "category": "guest",
    "subfolder_path": [
      "02_Guest_Lectures",
      "2026-09-19 - Agentic AI in Industry (Ayush Kumar Shah)"
    ],
    "summary": "Guest Lecture: Agentic AI in Industry with Meta's Ayush Kumar Shah"
  },
  {
    "id": "1v9R7eH8kFotTNxgGn2AjmlgCWxlHVGKi",
    "name": "2026-05-13 - KSS_ Agentic Coding - Chat.txt",
    "type": "chat",
    "date": "2026-05-13",
    "category": "office_hours",
    "subfolder_path": [
      "03_Office_Hours_and_KSS",
      "2026-05-13 - KSS - Agentic Coding"
    ],
    "summary": "KSS: Agentic Coding"
  },
  {
    "id": "1b0SDdJT0QcW0hA_X7epu_VRYy9y9jvhG",
    "name": "2026-05-13 - KSS_ Agentic Coding - Recording.mp4",
    "type": "video",
    "date": "2026-05-13",
    "category": "office_hours",
    "subfolder_path": [
      "03_Office_Hours_and_KSS",
      "2026-05-13 - KSS - Agentic Coding"
    ],
    "summary": "KSS: Agentic Coding"
  },
  {
    "id": "1NwBbff6msZ9xiz_Ib9wxmrFyh6uqqQK3",
    "name": "2026-06-18 - Office hour_ Linear Models - Chat.txt",
    "type": "chat",
    "date": "2026-06-18",
    "category": "office_hours",
    "subfolder_path": [
      "03_Office_Hours_and_KSS",
      "2026-06-18 - Office hour - Linear Models"
    ],
    "summary": "Office hour: Linear Models"
  },
  {
    "id": "1d9uSGGLuFd8Lstk4ntF4TEH0pawqRKgA",
    "name": "2026-06-18 - Office hour_ Linear Models - Recording.mp4",
    "type": "video",
    "date": "2026-06-18",
    "category": "office_hours",
    "subfolder_path": [
      "03_Office_Hours_and_KSS",
      "2026-06-18 - Office hour - Linear Models"
    ],
    "summary": "Office hour: Linear Models"
  },
  {
    "id": "19uB9jj0ZsZDjwyTS9eXSWzbekkvzWJ2J",
    "name": "2026-06-19 - Office hour_ Trees and Ensemble Models - Recording.mp4",
    "type": "video",
    "date": "2026-06-19",
    "category": "office_hours",
    "subfolder_path": [
      "03_Office_Hours_and_KSS",
      "2026-06-19 - Office hour - Trees and Ensemble Models"
    ],
    "summary": "Office hour: Trees and Ensemble Models"
  },
  {
    "id": "1YEFjYg4rKz0CLUaeM8r6DNvctPa8mTGn",
    "name": "2026-06-30 - Office hour _ Forecasting - Chat.txt",
    "type": "chat",
    "date": "2026-06-30",
    "category": "office_hours",
    "subfolder_path": [
      "03_Office_Hours_and_KSS",
      "2026-06-30 - Office hour  - Forecasting"
    ],
    "summary": "Office hour : Forecasting"
  },
  {
    "id": "1900-ImniL1_VW8E4QJM5mxTgY67m7zUJ",
    "name": "2026-06-30 - Office hour _ Forecasting - Recording.mp4",
    "type": "video",
    "date": "2026-06-30",
    "category": "office_hours",
    "subfolder_path": [
      "03_Office_Hours_and_KSS",
      "2026-06-30 - Office hour  - Forecasting"
    ],
    "summary": "Office hour : Forecasting"
  },
  {
    "id": "1epCfvqZhd_nNPh1xrGIOw6u9gG31XIyG",
    "name": "2026-07-07 - Office hour _ Artificial Neural Nets & Training Dynamics - Chat.txt",
    "type": "chat",
    "date": "2026-07-07",
    "category": "office_hours",
    "subfolder_path": [
      "03_Office_Hours_and_KSS",
      "2026-07-07 - Office hour  - Artificial Neural Nets & Training Dynamics"
    ],
    "summary": "Office hour : Artificial Neural Nets & Training Dynamics"
  },
  {
    "id": "18LKHPpPk02lI1bzlMydlMo20YPBB-g6Y",
    "name": "2026-07-07 - Office hour _ Artificial Neural Nets & Training Dynamics - Recording.mp4",
    "type": "video",
    "date": "2026-07-07",
    "category": "office_hours",
    "subfolder_path": [
      "03_Office_Hours_and_KSS",
      "2026-07-07 - Office hour  - Artificial Neural Nets & Training Dynamics"
    ],
    "summary": "Office hour : Artificial Neural Nets & Training Dynamics"
  },
  {
    "id": "1UGcZtTe1ZgO-HoqDEyDhTO9816UkAkJE",
    "name": "2026-07-07 - Office hour _ Artificial Neural Nets & Training Dynamics - Recording.mp4",
    "type": "video",
    "date": "2026-07-07",
    "category": "office_hours",
    "subfolder_path": [
      "03_Office_Hours_and_KSS",
      "2026-07-07 - Office hour  - Artificial Neural Nets & Training Dynamics"
    ],
    "summary": "Office hour : Artificial Neural Nets & Training Dynamics"
  },
  {
    "id": "1h7ZGakZzKCfHVoQl-4vI0fGWYwtTSH8A",
    "name": "2026-07-21 - Office hour _ Computer Vision - Recording.mp4",
    "type": "video",
    "date": "2026-07-21",
    "category": "office_hours",
    "subfolder_path": [
      "03_Office_Hours_and_KSS",
      "2026-07-21 - Office hour  - Computer Vision"
    ],
    "summary": "Office hour : Computer Vision"
  },
  {
    "id": "1Z7NyNiKnmkkOieSYgiTeaslacOFE3J0R",
    "name": "2026-08-11 - Office hour _Transformers, LLMs and Foundation Models - Chat.txt",
    "type": "chat",
    "date": "2026-08-11",
    "category": "office_hours",
    "subfolder_path": [
      "03_Office_Hours_and_KSS",
      "2026-08-11 - Office hour  -Transformers, LLMs and Foundation Models"
    ],
    "summary": "Office hour :Transformers, LLMs and Foundation Models"
  },
  {
    "id": "1yDxiTt5kV4lva9Y1J8s0MktnaxqunEKY",
    "name": "2026-08-11 - Office hour _Transformers, LLMs and Foundation Models - Recording.mp4",
    "type": "video",
    "date": "2026-08-11",
    "category": "office_hours",
    "subfolder_path": [
      "03_Office_Hours_and_KSS",
      "2026-08-11 - Office hour  -Transformers, LLMs and Foundation Models"
    ],
    "summary": "Office hour :Transformers, LLMs and Foundation Models"
  },
  {
    "id": "1PqKp0lulS38QQJJp9YDSBtCo-XcXDDyd",
    "name": "2026-09-01 - Office hour 11 _ Applied System - Recording.mp4",
    "type": "video",
    "date": "2026-09-01",
    "category": "office_hours",
    "subfolder_path": [
      "03_Office_Hours_and_KSS",
      "2026-09-01 - Office hour 11  - Applied System"
    ],
    "summary": "Office hour 11 : Applied System"
  },
  {
    "id": "1C6nUAcSicHOjyhrjd6vNki_N9h9V-K1O",
    "name": "2026-07-20 - TA Session_ Bimarsha Khanal - Chat.txt",
    "type": "chat",
    "date": "2026-07-20",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1mNI9P6k7wO3t3q2lo5fLR4vkZkikbgO4",
    "name": "2026-07-20 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-07-20",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1edkaefQsnSI4MSzLS5vcMZh31p-Akx22",
    "name": "2026-07-24 - TA Session_ Bimarsha Khanal - Chat.txt",
    "type": "chat",
    "date": "2026-07-24",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1eCxlXrdfGXCLVucuXxGAxOr9sLpftFl0",
    "name": "2026-07-24 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-07-24",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1Ln9FuwutFdzKXhORnno3mEtqi_lBMIWZ",
    "name": "2026-07-27 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-07-27",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1HCeIu95_6MVM-UNmhwBWKsUloP9XXCBo",
    "name": "2026-07-31 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-07-31",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1drqSRh5tvtn2_YJybdBudPqICrsNSkaa",
    "name": "2026-07-31 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-07-31",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1Z-BY03o3F2MaHgYw2Cn8Sh9PVujdsY0E",
    "name": "2026-08-03 - TA Session_ Bimarsha Khanal - Chat.txt",
    "type": "chat",
    "date": "2026-08-03",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1NBQSypkJ0ZQzKWYyKfZT-VOWUhK1awRI",
    "name": "2026-08-03 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-08-03",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1P8ozK8HF_oLdrOLqKByB1my2_aKV1KbS",
    "name": "2026-08-07 - TA Session_ Bimarsha Khanal - Chat.txt",
    "type": "chat",
    "date": "2026-08-07",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1wOSub1oG7xFiDn0IH15sK-W_s_-3LO6q",
    "name": "2026-08-07 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-08-07",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1PLE9iRO2cXKRXux_vy8Y8KIuavAh8NQM",
    "name": "2026-08-10 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-08-10",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1Dj0jSCbM71wMgzsmplAOG5kqHWigSQjl",
    "name": "2026-08-14 - TA Session_ Bimarsha Khanal - Chat.txt",
    "type": "chat",
    "date": "2026-08-14",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1Ez32wvIHRfvXo1MeG157QJ9DxHukQOdp",
    "name": "2026-08-14 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-08-14",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1fBLNiWzB7T6_TjgGhYalHjeNBkFzgTJl",
    "name": "2026-08-14 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-08-14",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1yLzNj8OIEBWq6MwlG6le1wf1zpwY1sDk",
    "name": "2026-08-31 - TA Session_ Bimarsha Khanal - Chat.txt",
    "type": "chat",
    "date": "2026-08-31",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1Mkk2hWIBUQjr-ELt2KUtuINDTtOPf0xw",
    "name": "2026-08-31 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-08-31",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "13a2CAtrww7pSxEny3kLxjnXTTbAQ8afp",
    "name": "2026-09-04 - TA Session_ Bimarsha Khanal - Chat.txt",
    "type": "chat",
    "date": "2026-09-04",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1pk58gZG92OWO0kXEft3UtUI4pt7Z48i6",
    "name": "2026-09-04 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-09-04",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1YRwrIrJofL8klOHDo11jx1QhCIk-3nVe",
    "name": "2026-09-11 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-09-11",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1Bm9h81WnixfQNy8J8o3En06tjXe6PkBM",
    "name": "2026-09-14 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-09-14",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1C4kP0GYC4DVrZsJ6XeGyBqtZDYjpYTQG",
    "name": "2026-09-18 - TA Session_ Bimarsha Khanal - Chat.txt",
    "type": "chat",
    "date": "2026-09-18",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1_ETgSAYFzY1ocPSgYpHS3pJYz0yhRIyL",
    "name": "2026-09-18 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-09-18",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1DLL0u4UvQCHTWUP5VsUO5Lc1x73rr_Se",
    "name": "2026-09-21 - TA Session_ Bimarsha Khanal - Chat.txt",
    "type": "chat",
    "date": "2026-09-21",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1UBmnFoy8rjO3L4LEHwLAEGfjTxtM5-7n",
    "name": "2026-09-21 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-09-21",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1bho3MCiNcYuKLLluY-vYNhMN479Gzier",
    "name": "2026-09-25 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-09-25",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "10IXJUJ1ldLZ8TVOdBzJVeuxQG8Oa6st4",
    "name": "2026-09-28 - TA Session_ Bimarsha Khanal - Chat.txt",
    "type": "chat",
    "date": "2026-09-28",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1gg3hGSFWugXEubPFeWOtVqXAj7JNLqMS",
    "name": "2026-09-28 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-09-28",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1znsODtwdQz5Y_iMzLuKASvS6fxoC-okJ",
    "name": "2026-10-02 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-10-02",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1aKYivL6XK0X1MdTJI0gQDzzv_ztFiNUG",
    "name": "2026-10-05 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-10-05",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1FSiocPh4HXkWHA9IKKnD9QADjkY3r4pR",
    "name": "2026-10-09 - TA Session_ Bimarsha Khanal - Chat.txt",
    "type": "chat",
    "date": "2026-10-09",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1Vwk-BMwpBP8-rGTJFeLKlOP7Xh7_HDX8",
    "name": "2026-10-09 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-10-09",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1tzRg4Vx0KHpxMHlg3BUi2KFlSS1WNrqq",
    "name": "2026-10-09 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-10-09",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1T2IJJ0giSLDQJO7nLwfwgNMKMHQZP7kS",
    "name": "2026-10-12 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-10-12",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1pcAH5iviEbTNaY2a6E2lJUMwXN64_MRf",
    "name": "2026-10-15 - TA Session_ Bimarsha Khanal - Chat.txt",
    "type": "chat",
    "date": "2026-10-15",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "15za-gQjAjg1G1hY1bQYBuZlKVIUEmSro",
    "name": "2026-10-15 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-10-15",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "13fGoucBqyvbjvROT4rqhvIWBf9-WaHrP",
    "name": "2026-10-15 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "type": "video",
    "date": "2026-10-15",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Bimarsha Khanal"
    ],
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1XxCLQwaJWmiCCIF1LHDNr9pxWhyEq4td",
    "name": "2026-07-20 - TA Session_ Pawan Sapkota - Chat.txt",
    "type": "chat",
    "date": "2026-07-20",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1CnGY1TVqE4FI9fT3fDyzFk2N2QF53ocK",
    "name": "2026-07-20 - TA Session_ Pawan Sapkota - Recording.mp4",
    "type": "video",
    "date": "2026-07-20",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1PdTjmETFU5GjCVCRpAEwlHNEwjfIo7uI",
    "name": "2026-07-27 - TA Session_ Pawan Sapkota - Chat.txt",
    "type": "chat",
    "date": "2026-07-27",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1aBT8V4452Mw9SfB4GPcYGmRC4xA9Rxvh",
    "name": "2026-07-27 - TA Session_ Pawan Sapkota - Recording.mp4",
    "type": "video",
    "date": "2026-07-27",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "12pg6azRMZnjfgbZvlT_JQjeGrai3fxRS",
    "name": "2026-08-04 - TA Session_ Pawan Sapkota - Chat.txt",
    "type": "chat",
    "date": "2026-08-04",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1AyRW6yfsxk4M6KMg1xsutk6Ift4PKoiX",
    "name": "2026-08-04 - TA Session_ Pawan Sapkota - Recording.mp4",
    "type": "video",
    "date": "2026-08-04",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1yYvsGMNEFPYEPtNjFG2PSseRoDKg7C83",
    "name": "2026-08-10 - TA Session_ Pawan Sapkota - Chat.txt",
    "type": "chat",
    "date": "2026-08-10",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1n-b70nWfPbQJMQFDTdYXMVzqIzS9FK3p",
    "name": "2026-08-10 - TA Session_ Pawan Sapkota - Recording.mp4",
    "type": "video",
    "date": "2026-08-10",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1X7AI-gPAkLVwEFmko2dKKsjJlEmKYw78",
    "name": "2026-09-01 - TA Session_ Pawan Sapkota - Chat.txt",
    "type": "chat",
    "date": "2026-09-01",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1nRNCtr_meGmmfH3QAdREgYednJ-4wN2u",
    "name": "2026-09-01 - TA Session_ Pawan Sapkota - Recording.mp4",
    "type": "video",
    "date": "2026-09-01",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1WWvUbM2cWvigfQGOdDBYL0py8HodN_g8",
    "name": "2026-09-06 - TA Session_ Pawan Sapkota - Chat.txt",
    "type": "chat",
    "date": "2026-09-06",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1xuSOnvzhioPioQJOSJa8pm2p9lSkr6-X",
    "name": "2026-09-06 - TA Session_ Pawan Sapkota - Recording.mp4",
    "type": "video",
    "date": "2026-09-06",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "14K9cd_b1Loyp_LLwSNebmV3z7dpPpRK_",
    "name": "2026-09-11 - TA Session_ Pawan Sapkota - Recording.mp4",
    "type": "video",
    "date": "2026-09-11",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "13QhUEY1dZmrOo2Ix5U3qcDC6bmhWwFdy",
    "name": "2026-09-21 - TA Session_ Pawan Sapkota - Chat.txt",
    "type": "chat",
    "date": "2026-09-21",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "13KqfgyPNHX5TwSAaAu-vTQ4NZ9KoTcpu",
    "name": "2026-09-21 - TA Session_ Pawan Sapkota - Recording.mp4",
    "type": "video",
    "date": "2026-09-21",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1pdlPfaCPvyUq9fdqETlNYT2I7kGkgXHv",
    "name": "2026-09-28 - TA Session_ Pawan Sapkota - Chat.txt",
    "type": "chat",
    "date": "2026-09-28",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1FM7fGm2RiwvSYPNIWSowkm2I9W_buaG6",
    "name": "2026-09-28 - TA Session_ Pawan Sapkota - Recording.mp4",
    "type": "video",
    "date": "2026-09-28",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1pNEHTd65SZDUz_AXqgycV1NLMxstpZCd",
    "name": "2026-10-06 - TA Session_ Pawan Sapkota - Recording.mp4",
    "type": "video",
    "date": "2026-10-06",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1CGecm4V4Ky66o-uiha4W7kj-5AbKpj9s",
    "name": "2026-10-12 - TA Session_ Pawan Sapkota - Chat.txt",
    "type": "chat",
    "date": "2026-10-12",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1lFU2LshZUcgI74jOrCO8MKKXKMmrUJmY",
    "name": "2026-10-12 - TA Session_ Pawan Sapkota - Recording.mp4",
    "type": "video",
    "date": "2026-10-12",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1R1gPZ0PY81RpS_58bXD0TvC6AOIgbFsW",
    "name": "2026-10-12 - TA Session_ Pawan Sapkota - Recording.mp4",
    "type": "video",
    "date": "2026-10-12",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Pawan Sapkota"
    ],
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1O2sA9tOgIzRw4XFnjP4gK8WANsnCO9B2",
    "name": "2026-07-20 - TA Session_ Raj Kumar Bishwakarma - Recording.mp4",
    "type": "video",
    "date": "2026-07-20",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Bishwakarma"
  },
  {
    "id": "1K17URw2zDzG77tzCh2oNM8lzoL3YsaAS",
    "name": "2026-07-24 - TA Session_ Raj Kumar Bishwakarma - Chat.txt",
    "type": "chat",
    "date": "2026-07-24",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Bishwakarma"
  },
  {
    "id": "1g1jz2ALO0YFjH4p8EvUPhHhi2GolXKJP",
    "name": "2026-07-24 - TA Session_ Raj Kumar Bishwakarma - Recording.mp4",
    "type": "video",
    "date": "2026-07-24",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Bishwakarma"
  },
  {
    "id": "1Wn7ZoVDRmLt4Xx7aHH6zHhGgFdTN53dH",
    "name": "2026-07-27 - TA Session_ Raj Kumar Bishwakarma - Recording.mp4",
    "type": "video",
    "date": "2026-07-27",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Bishwakarma"
  },
  {
    "id": "1LhkOEYr8xZPWUVUpuYjrmz4RsS-Hbbou",
    "name": "2026-07-31 - TA Session_ Raj Kumar Bishwakarma - Recording.mp4",
    "type": "video",
    "date": "2026-07-31",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Bishwakarma"
  },
  {
    "id": "1DJbxG0sDXxwaQ-wa04AGRvUR6gwq4TOi",
    "name": "2026-08-03 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "type": "video",
    "date": "2026-08-03",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1xI5DnLJkFYkEejiZ-P2tX06scNiPpjZJ",
    "name": "2026-08-11 - TA Session_ Raj Kumar Biswokarma - Chat.txt",
    "type": "chat",
    "date": "2026-08-11",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1XSYWnppqw-rWgd7-AVgWh4-hpEyr2535",
    "name": "2026-08-11 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "type": "video",
    "date": "2026-08-11",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1eet0z6wbBD8Wh3HClXV0TpACo4IL6MZl",
    "name": "2026-09-01 - TA Session_ Raj Kumar Biswokarma - Chat.txt",
    "type": "chat",
    "date": "2026-09-01",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1V3TBB8ADB_8yEhiw1arr_0QmjTWCWKsY",
    "name": "2026-09-01 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "type": "video",
    "date": "2026-09-01",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1kCB8s7g6a7h3xp8juWi8RuHz4IpfDHh8",
    "name": "2026-09-04 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "type": "video",
    "date": "2026-09-04",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1IJiHPnhrbyR73MPIAmfaAZmeSQ-Nm7GP",
    "name": "2026-09-14 - TA Session_ Raj Kumar Biswokarma - Chat.txt",
    "type": "chat",
    "date": "2026-09-14",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1_wkdcIR4-qDpHpNIhj6iMzr7KPk4XHw9",
    "name": "2026-09-14 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "type": "video",
    "date": "2026-09-14",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1M_0Eh58f39EsR_clChnRZxurnlhyd_-g",
    "name": "2026-09-21 - TA Session_ Raj Kumar Biswokarma - Chat.txt",
    "type": "chat",
    "date": "2026-09-21",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1is6aYqK7xPk9DYJOXVHnZUdHwewnsbZX",
    "name": "2026-09-21 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "type": "video",
    "date": "2026-09-21",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1UUV7a74-BTQwxFJVjyRGRhWwkRHwX1X2",
    "name": "2026-09-25 - TA Session_ Raj Kumar Bishwokarma - Recording.mp4",
    "type": "video",
    "date": "2026-09-25",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Bishwokarma"
  },
  {
    "id": "1OsYExmMGzIIkJWTrqa4F-BCH2W37X3WX",
    "name": "2026-09-28 - TA Session_ Raj Kumar Biswokarma - Chat.txt",
    "type": "chat",
    "date": "2026-09-28",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1q9ObChzWim0208z9idNpQpbHvr4IYOz5",
    "name": "2026-09-28 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "type": "video",
    "date": "2026-09-28",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1oKG7V7F28hKamnrw64dBgvcukApcZVKr",
    "name": "2026-10-05 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "type": "video",
    "date": "2026-10-05",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1WvXbCKwPVxJtcnieGnJoZrfxRV4ai-BH",
    "name": "2026-10-12 - TA Session_ Raj Kumar Biswokarma - Chat.txt",
    "type": "chat",
    "date": "2026-10-12",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1cqQRbuVxNopFwqK3Cp783mpuouvh5ftE",
    "name": "2026-10-12 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "type": "video",
    "date": "2026-10-12",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Raj Kumar Bishwakarma"
    ],
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1rSkVx5i_XBqpTC8LGfcygXyqFVK2FZn-",
    "name": "2026-07-24 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "type": "video",
    "date": "2026-07-24",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "174zT62Z_tcXsq5bAVAhx4WsED7Xo4xU4",
    "name": "2026-07-26 - TA Session_ Rakshya Lama Moktan - Chat.txt",
    "type": "chat",
    "date": "2026-07-26",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1tQYKi8KysWTAK_tGwMkZFf9TkJ0gHBWJ",
    "name": "2026-07-26 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "type": "video",
    "date": "2026-07-26",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1gtnx5M3Ks9rKXcKhiio6jziVu3YECvFx",
    "name": "2026-07-26 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "type": "video",
    "date": "2026-07-26",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1VJn2t52MYO7IEcJ_45dLjTYU4be9u2VB",
    "name": "2026-07-26 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "type": "video",
    "date": "2026-07-26",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "10Qzidz3e67VjJ1k8ezIQetNw4mDCEDnG",
    "name": "2026-07-29 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "type": "video",
    "date": "2026-07-29",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "14cUR1EldGDFPv73hgs23deFKhGvznBVQ",
    "name": "2026-07-31 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "type": "video",
    "date": "2026-07-31",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1qrSPbqC-woga4AiImssdWVB-pfQpMKHR",
    "name": "2026-08-05 - TA Session_ Rakshya Lama Moktan - Chat.txt",
    "type": "chat",
    "date": "2026-08-05",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1yn-Ozr_KG3bfrl7vRLJ1yXcxyijI0Qag",
    "name": "2026-08-05 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "type": "video",
    "date": "2026-08-05",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1kRvp3TgFJJRhsu2HYND7y1Is_3XPW-ye",
    "name": "2026-08-07 - TA Session_ Rakshya Lama Moktan - Chat.txt",
    "type": "chat",
    "date": "2026-08-07",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "12eDuxDntz_tg_TgFXtKq-OouHu6tyeTx",
    "name": "2026-08-07 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "type": "video",
    "date": "2026-08-07",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1ItkTmv9GbRsyESA9sEkc5knB4A7MetDi",
    "name": "2026-09-02 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "type": "video",
    "date": "2026-09-02",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1nh3Q8pSC3kxaJJGikXAIU3uhPSK00vlg",
    "name": "2026-09-23 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "type": "video",
    "date": "2026-09-23",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1YK917deP9dxoZjlkEhD_G0YRVWfpOSO6",
    "name": "2026-09-27 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "type": "video",
    "date": "2026-09-27",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1_L5xoKcj0yMnDaLF3jSBleMApuVZWS1v",
    "name": "2026-09-30 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "type": "video",
    "date": "2026-09-30",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1NpvqWSA0zeYW-Oh2xvJrhbU_6dypai9R",
    "name": "2026-10-08 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "type": "video",
    "date": "2026-10-08",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "17zKJfJTKQEq9KgF6HWIu7YdMWBHVWN0J",
    "name": "2026-10-11 - TA Session_ Rakshya Lama Moktan - Chat.txt",
    "type": "chat",
    "date": "2026-10-11",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "196aheWwq19J2WfGAgyyN6JYO4H9XGRvL",
    "name": "2026-10-11 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "type": "video",
    "date": "2026-10-11",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Rakshya Lama Moktan"
    ],
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1pXomMgIBIKB2TMIrv4JcrL6_KpzYJBzv",
    "name": "2026-07-20 - TA Session_ Shreejan Kisee - Chat.txt",
    "type": "chat",
    "date": "2026-07-20",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Shreejan Kisee"
    ],
    "summary": "TA Session: Shreejan Kisee"
  },
  {
    "id": "1OQwbdIMxrrYtipFWMstl9GreUo8c9J2X",
    "name": "2026-07-20 - TA Session_ Shreejan Kisee - Recording.mp4",
    "type": "video",
    "date": "2026-07-20",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Shreejan Kisee"
    ],
    "summary": "TA Session: Shreejan Kisee"
  },
  {
    "id": "1EouAxsRVz3z-gscF8XIUL6GAfaLbzPIz",
    "name": "2026-07-27 - TA Session_ Shreejan Kisee - Chat.txt",
    "type": "chat",
    "date": "2026-07-27",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Shreejan Kisee"
    ],
    "summary": "TA Session: Shreejan Kisee"
  },
  {
    "id": "1kspPtJzvA_rMfzhC-g5pxNTCrE2CeHqA",
    "name": "2026-07-27 - TA Session_ Shreejan Kisee - Recording.mp4",
    "type": "video",
    "date": "2026-07-27",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Shreejan Kisee"
    ],
    "summary": "TA Session: Shreejan Kisee"
  },
  {
    "id": "1Mq210GRSZDmAU9HgEgD4f3oSmYTE19b1",
    "name": "2026-07-30 - TA Session_ Shreejan Kiseee - Chat.txt",
    "type": "chat",
    "date": "2026-07-30",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Shreejan Kisee"
    ],
    "summary": "TA Session: Shreejan Kiseee"
  },
  {
    "id": "1SQFCIFttgizEROz5T6oP71c66ma69H-w",
    "name": "2026-07-30 - TA Session_ Shreejan Kiseee - Recording.mp4",
    "type": "video",
    "date": "2026-07-30",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Shreejan Kisee"
    ],
    "summary": "TA Session: Shreejan Kiseee"
  },
  {
    "id": "1oqpfh3Y90RZYoh7qYrSIpSVqjr37mtrw",
    "name": "2026-08-03 - TA Session_ Shreejan Kisee - Chat.txt",
    "type": "chat",
    "date": "2026-08-03",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Shreejan Kisee"
    ],
    "summary": "TA Session: Shreejan Kisee"
  },
  {
    "id": "11rJhloF-8g3WGV6qv_T5VIXDGEXJ5w_D",
    "name": "2026-08-03 - TA Session_ Shreejan Kisee - Recording.mp4",
    "type": "video",
    "date": "2026-08-03",
    "category": "ta",
    "subfolder_path": [
      "04_TA_Sessions",
      "Shreejan Kisee"
    ],
    "summary": "TA Session: Shreejan Kisee"
  }
];
