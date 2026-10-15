/**
 * Google Apps Script to Batch Copy AI Fellowship Recordings Directly to Google Drive
 * 
 * Instructions:
 * 1. Go to https://script.new in your browser (logged in with your fellowship Google account).
 * 2. Delete any boilerplate and paste this entire code.
 * 3. Click "Run" (makeCopiesOfRecordings).
 * 4. Grant permissions when prompted.
 * 5. All video files will be copied directly into a folder named "AI Fellowship 2026 Recordings" in your Google Drive!
 */

function makeCopiesOfRecordings() {
  var folderName = "AI Fellowship 2026 Recordings";
  var folders = DriveApp.getFoldersByName(folderName);
  var targetFolder;
  
  if (folders.hasNext()) {
    targetFolder = folders.next();
    Logger.log("Using existing folder: " + folderName);
  } else {
    targetFolder = DriveApp.createFolder(folderName);
    Logger.log("Created target folder: " + folderName);
  }
  
  var files = [
  {
    "id": "1Lacuvn9XCxFMvVPwV3hE3Pl4azOXfMRL",
    "name": "2026-05-03 - Week 1 _ Data Wrangling - Recording.mp4",
    "date": "2026-05-03",
    "summary": "Week 1 : Data Wrangling"
  },
  {
    "id": "17V2kGNbowAdEYu1Je6UOwwlE7fZyTyfZ",
    "name": "2026-05-10 - Week 2_ Agentic Software Development - Recording.mp4",
    "date": "2026-05-10",
    "summary": "Week 2: Agentic Software Development"
  },
  {
    "id": "1b0SDdJT0QcW0hA_X7epu_VRYy9y9jvhG",
    "name": "2026-05-13 - KSS_ Agentic Coding - Recording.mp4",
    "date": "2026-05-13",
    "summary": "KSS: Agentic Coding"
  },
  {
    "id": "1U4fI4OgnMcd8oloW2GCU0DVS-0XO6kjh",
    "name": "2026-05-17 - Week 3_ Generative AI, Prompt Engineering, Agentic AI Overview - Recording.mp4",
    "date": "2026-05-17",
    "summary": "Week 3: Generative AI, Prompt Engineering, Agentic AI Overview"
  },
  {
    "id": "1QaE5JROBtKjh1YeAFuqqboDLQqEhWX-m",
    "name": "2026-05-24 - Week 4_ Linear Models - Recording.mp4",
    "date": "2026-05-24",
    "summary": "Week 4: Linear Models"
  },
  {
    "id": "1z93ntSHWeK8z5D4pIfVBki4CzF_YGKQ7",
    "name": "2026-05-25 - Week 4_ Linear Models (Rescheduled) - Recording.mp4",
    "date": "2026-05-25",
    "summary": "Week 4: Linear Models (Rescheduled)"
  },
  {
    "id": "1ZPzjrgVk4mv6PWDEPWA3KEZddW1lPxw_",
    "name": "2026-05-31 - Week 5_ Trees and Ensemble Method - Recording.mp4",
    "date": "2026-05-31",
    "summary": "Week 5: Trees and Ensemble Method"
  },
  {
    "id": "1shmztjOvaFYviSCz380LXdCSpbOOSKZk",
    "name": "2026-06-07 - Week 6_ Probabilistic Models - Recording.mp4",
    "date": "2026-06-07",
    "summary": "Week 6: Probabilistic Models"
  },
  {
    "id": "1d9uSGGLuFd8Lstk4ntF4TEH0pawqRKgA",
    "name": "2026-06-18 - Office hour_ Linear Models - Recording.mp4",
    "date": "2026-06-18",
    "summary": "Office hour: Linear Models"
  },
  {
    "id": "19uB9jj0ZsZDjwyTS9eXSWzbekkvzWJ2J",
    "name": "2026-06-19 - Office hour_ Trees and Ensemble Models - Recording.mp4",
    "date": "2026-06-19",
    "summary": "Office hour: Trees and Ensemble Models"
  },
  {
    "id": "1xYt-cvPOciP3dOWKwuSq7fGs03I2mgBL",
    "name": "2026-06-21 - Week 7 _ Clustering - Recording.mp4",
    "date": "2026-06-21",
    "summary": "Week 7 : Clustering"
  },
  {
    "id": "19lDCFpN2xORbdxOeKaY-jXaESXReTOEn",
    "name": "2026-06-28 - Week 8 _ Forecasting - Recording.mp4",
    "date": "2026-06-28",
    "summary": "Week 8 : Forecasting"
  },
  {
    "id": "1900-ImniL1_VW8E4QJM5mxTgY67m7zUJ",
    "name": "2026-06-30 - Office hour _ Forecasting - Recording.mp4",
    "date": "2026-06-30",
    "summary": "Office hour : Forecasting"
  },
  {
    "id": "18LKHPpPk02lI1bzlMydlMo20YPBB-g6Y",
    "name": "2026-07-07 - Office hour _ Artificial Neural Nets & Training Dynamics - Recording.mp4",
    "date": "2026-07-07",
    "summary": "Office hour : Artificial Neural Nets & Training Dynamics"
  },
  {
    "id": "1UGcZtTe1ZgO-HoqDEyDhTO9816UkAkJE",
    "name": "2026-07-07 - Office hour _ Artificial Neural Nets & Training Dynamics - Recording.mp4",
    "date": "2026-07-07",
    "summary": "Office hour : Artificial Neural Nets & Training Dynamics"
  },
  {
    "id": "1zHbp2-7HZuM4TDLMi1VQRvcV_qJ1Klp0",
    "name": "2026-07-12 - Week 10 _ Handling Image Data - Recording.mp4",
    "date": "2026-07-12",
    "summary": "Week 10 : Handling Image Data"
  },
  {
    "id": "1aCXq6l0zdH6JOuW_tbdeF7wyDLbYKDq2",
    "name": "2026-07-19 - Week 11_ Computer Vision - Recording.mp4",
    "date": "2026-07-19",
    "summary": "Week 11: Computer Vision"
  },
  {
    "id": "1mNI9P6k7wO3t3q2lo5fLR4vkZkikbgO4",
    "name": "2026-07-20 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-07-20",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1CnGY1TVqE4FI9fT3fDyzFk2N2QF53ocK",
    "name": "2026-07-20 - TA Session_ Pawan Sapkota - Recording.mp4",
    "date": "2026-07-20",
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1O2sA9tOgIzRw4XFnjP4gK8WANsnCO9B2",
    "name": "2026-07-20 - TA Session_ Raj Kumar Bishwakarma - Recording.mp4",
    "date": "2026-07-20",
    "summary": "TA Session: Raj Kumar Bishwakarma"
  },
  {
    "id": "1OQwbdIMxrrYtipFWMstl9GreUo8c9J2X",
    "name": "2026-07-20 - TA Session_ Shreejan Kisee - Recording.mp4",
    "date": "2026-07-20",
    "summary": "TA Session: Shreejan Kisee"
  },
  {
    "id": "1h7ZGakZzKCfHVoQl-4vI0fGWYwtTSH8A",
    "name": "2026-07-21 - Office hour _ Computer Vision - Recording.mp4",
    "date": "2026-07-21",
    "summary": "Office hour : Computer Vision"
  },
  {
    "id": "1eCxlXrdfGXCLVucuXxGAxOr9sLpftFl0",
    "name": "2026-07-24 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-07-24",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1g1jz2ALO0YFjH4p8EvUPhHhi2GolXKJP",
    "name": "2026-07-24 - TA Session_ Raj Kumar Bishwakarma - Recording.mp4",
    "date": "2026-07-24",
    "summary": "TA Session: Raj Kumar Bishwakarma"
  },
  {
    "id": "1rSkVx5i_XBqpTC8LGfcygXyqFVK2FZn-",
    "name": "2026-07-24 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "date": "2026-07-24",
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1tQYKi8KysWTAK_tGwMkZFf9TkJ0gHBWJ",
    "name": "2026-07-26 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "date": "2026-07-26",
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1gtnx5M3Ks9rKXcKhiio6jziVu3YECvFx",
    "name": "2026-07-26 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "date": "2026-07-26",
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1VJn2t52MYO7IEcJ_45dLjTYU4be9u2VB",
    "name": "2026-07-26 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "date": "2026-07-26",
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "16zA2Ko6znIvvjpzEiREmdQQQbzyy1s6W",
    "name": "2026-07-26 - Week 12 _ Natural Language Processing - Recording.mp4",
    "date": "2026-07-26",
    "summary": "Week 12 : Natural Language Processing"
  },
  {
    "id": "1Ln9FuwutFdzKXhORnno3mEtqi_lBMIWZ",
    "name": "2026-07-27 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-07-27",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1aBT8V4452Mw9SfB4GPcYGmRC4xA9Rxvh",
    "name": "2026-07-27 - TA Session_ Pawan Sapkota - Recording.mp4",
    "date": "2026-07-27",
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1Wn7ZoVDRmLt4Xx7aHH6zHhGgFdTN53dH",
    "name": "2026-07-27 - TA Session_ Raj Kumar Bishwakarma - Recording.mp4",
    "date": "2026-07-27",
    "summary": "TA Session: Raj Kumar Bishwakarma"
  },
  {
    "id": "1kspPtJzvA_rMfzhC-g5pxNTCrE2CeHqA",
    "name": "2026-07-27 - TA Session_ Shreejan Kisee - Recording.mp4",
    "date": "2026-07-27",
    "summary": "TA Session: Shreejan Kisee"
  },
  {
    "id": "10Qzidz3e67VjJ1k8ezIQetNw4mDCEDnG",
    "name": "2026-07-29 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "date": "2026-07-29",
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1SQFCIFttgizEROz5T6oP71c66ma69H-w",
    "name": "2026-07-30 - TA Session_ Shreejan Kiseee - Recording.mp4",
    "date": "2026-07-30",
    "summary": "TA Session: Shreejan Kiseee"
  },
  {
    "id": "1HCeIu95_6MVM-UNmhwBWKsUloP9XXCBo",
    "name": "2026-07-31 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-07-31",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1drqSRh5tvtn2_YJybdBudPqICrsNSkaa",
    "name": "2026-07-31 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-07-31",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1LhkOEYr8xZPWUVUpuYjrmz4RsS-Hbbou",
    "name": "2026-07-31 - TA Session_ Raj Kumar Bishwakarma - Recording.mp4",
    "date": "2026-07-31",
    "summary": "TA Session: Raj Kumar Bishwakarma"
  },
  {
    "id": "14cUR1EldGDFPv73hgs23deFKhGvznBVQ",
    "name": "2026-07-31 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "date": "2026-07-31",
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "12vKi0LQaLjVgaWsC-GaZrkhKqwMVSRxk",
    "name": "2026-08-02 - Week 13_ Sequence Learning - Recording.mp4",
    "date": "2026-08-02",
    "summary": "Week 13: Sequence Learning"
  },
  {
    "id": "1NBQSypkJ0ZQzKWYyKfZT-VOWUhK1awRI",
    "name": "2026-08-03 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-08-03",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1DJbxG0sDXxwaQ-wa04AGRvUR6gwq4TOi",
    "name": "2026-08-03 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "date": "2026-08-03",
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "11rJhloF-8g3WGV6qv_T5VIXDGEXJ5w_D",
    "name": "2026-08-03 - TA Session_ Shreejan Kisee - Recording.mp4",
    "date": "2026-08-03",
    "summary": "TA Session: Shreejan Kisee"
  },
  {
    "id": "1AyRW6yfsxk4M6KMg1xsutk6Ift4PKoiX",
    "name": "2026-08-04 - TA Session_ Pawan Sapkota - Recording.mp4",
    "date": "2026-08-04",
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1yn-Ozr_KG3bfrl7vRLJ1yXcxyijI0Qag",
    "name": "2026-08-05 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "date": "2026-08-05",
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1wOSub1oG7xFiDn0IH15sK-W_s_-3LO6q",
    "name": "2026-08-07 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-08-07",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "12eDuxDntz_tg_TgFXtKq-OouHu6tyeTx",
    "name": "2026-08-07 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "date": "2026-08-07",
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "10b8iMqPVYt72W3afU1TRIXX53h2riUSu",
    "name": "2026-08-09 - Week 14_ Transformers, LLMs and Foundation Models - Recording.mp4",
    "date": "2026-08-09",
    "summary": "Week 14: Transformers, LLMs and Foundation Models"
  },
  {
    "id": "1PLE9iRO2cXKRXux_vy8Y8KIuavAh8NQM",
    "name": "2026-08-10 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-08-10",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1n-b70nWfPbQJMQFDTdYXMVzqIzS9FK3p",
    "name": "2026-08-10 - TA Session_ Pawan Sapkota - Recording.mp4",
    "date": "2026-08-10",
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1yDxiTt5kV4lva9Y1J8s0MktnaxqunEKY",
    "name": "2026-08-11 - Office hour _Transformers, LLMs and Foundation Models - Recording.mp4",
    "date": "2026-08-11",
    "summary": "Office hour :Transformers, LLMs and Foundation Models"
  },
  {
    "id": "1XSYWnppqw-rWgd7-AVgWh4-hpEyr2535",
    "name": "2026-08-11 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "date": "2026-08-11",
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1Ez32wvIHRfvXo1MeG157QJ9DxHukQOdp",
    "name": "2026-08-14 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-08-14",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1fBLNiWzB7T6_TjgGhYalHjeNBkFzgTJl",
    "name": "2026-08-14 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-08-14",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "12Ohsw71eWUFTt5ngQY-fuMR4I2QiMAfH",
    "name": "2026-08-30 - Week 15_ Applied Systems - Recording.mp4",
    "date": "2026-08-30",
    "summary": "Week 15: Applied Systems"
  },
  {
    "id": "1Mkk2hWIBUQjr-ELt2KUtuINDTtOPf0xw",
    "name": "2026-08-31 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-08-31",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1PqKp0lulS38QQJJp9YDSBtCo-XcXDDyd",
    "name": "2026-09-01 - Office hour 11 _ Applied System - Recording.mp4",
    "date": "2026-09-01",
    "summary": "Office hour 11 : Applied System"
  },
  {
    "id": "1nRNCtr_meGmmfH3QAdREgYednJ-4wN2u",
    "name": "2026-09-01 - TA Session_ Pawan Sapkota - Recording.mp4",
    "date": "2026-09-01",
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1V3TBB8ADB_8yEhiw1arr_0QmjTWCWKsY",
    "name": "2026-09-01 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "date": "2026-09-01",
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1ItkTmv9GbRsyESA9sEkc5knB4A7MetDi",
    "name": "2026-09-02 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "date": "2026-09-02",
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1pk58gZG92OWO0kXEft3UtUI4pt7Z48i6",
    "name": "2026-09-04 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-09-04",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1kCB8s7g6a7h3xp8juWi8RuHz4IpfDHh8",
    "name": "2026-09-04 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "date": "2026-09-04",
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1xuSOnvzhioPioQJOSJa8pm2p9lSkr6-X",
    "name": "2026-09-06 - TA Session_ Pawan Sapkota - Recording.mp4",
    "date": "2026-09-06",
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1K2HtaX423AnO2SHZNphVrKCS-XXaOxB1",
    "name": "2026-09-06 - Week 16_ Agentic AI - Recording.mp4",
    "date": "2026-09-06",
    "summary": "Week 16: Agentic AI"
  },
  {
    "id": "1LaKaY_axemL2x1Lqr-3yBVMMuLByovhK",
    "name": "2026-09-06 - Week 16_ Agentic AI - Recording.mp4",
    "date": "2026-09-06",
    "summary": "Week 16: Agentic AI"
  },
  {
    "id": "1YRwrIrJofL8klOHDo11jx1QhCIk-3nVe",
    "name": "2026-09-11 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-09-11",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "14K9cd_b1Loyp_LLwSNebmV3z7dpPpRK_",
    "name": "2026-09-11 - TA Session_ Pawan Sapkota - Recording.mp4",
    "date": "2026-09-11",
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "185naIPDIGUgWcDIlb7QcVHvYYwzSs_ZN",
    "name": "2026-09-13 - Week 17_  AI Systems & MLOps - Recording.mp4",
    "date": "2026-09-13",
    "summary": "Week 17:  AI Systems & MLOps"
  },
  {
    "id": "1Bm9h81WnixfQNy8J8o3En06tjXe6PkBM",
    "name": "2026-09-14 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-09-14",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1_wkdcIR4-qDpHpNIhj6iMzr7KPk4XHw9",
    "name": "2026-09-14 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "date": "2026-09-14",
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1_ETgSAYFzY1ocPSgYpHS3pJYz0yhRIyL",
    "name": "2026-09-18 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-09-18",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1PuSz2wWj0ZLtc1_L1Np1cy60mCxwXrC3",
    "name": "2026-09-19 - Guest Lecture_ Agentic AI in Industry with Meta's Ayush Kumar Shah - Recording.mp4",
    "date": "2026-09-19",
    "summary": "Guest Lecture: Agentic AI in Industry with Meta's Ayush Kumar Shah"
  },
  {
    "id": "1UBmnFoy8rjO3L4LEHwLAEGfjTxtM5-7n",
    "name": "2026-09-21 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-09-21",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "13KqfgyPNHX5TwSAaAu-vTQ4NZ9KoTcpu",
    "name": "2026-09-21 - TA Session_ Pawan Sapkota - Recording.mp4",
    "date": "2026-09-21",
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1is6aYqK7xPk9DYJOXVHnZUdHwewnsbZX",
    "name": "2026-09-21 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "date": "2026-09-21",
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1nh3Q8pSC3kxaJJGikXAIU3uhPSK00vlg",
    "name": "2026-09-23 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "date": "2026-09-23",
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1bho3MCiNcYuKLLluY-vYNhMN479Gzier",
    "name": "2026-09-25 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-09-25",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1UUV7a74-BTQwxFJVjyRGRhWwkRHwX1X2",
    "name": "2026-09-25 - TA Session_ Raj Kumar Bishwokarma - Recording.mp4",
    "date": "2026-09-25",
    "summary": "TA Session: Raj Kumar Bishwokarma"
  },
  {
    "id": "1YK917deP9dxoZjlkEhD_G0YRVWfpOSO6",
    "name": "2026-09-27 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "date": "2026-09-27",
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1gg3hGSFWugXEubPFeWOtVqXAj7JNLqMS",
    "name": "2026-09-28 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-09-28",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1FM7fGm2RiwvSYPNIWSowkm2I9W_buaG6",
    "name": "2026-09-28 - TA Session_ Pawan Sapkota - Recording.mp4",
    "date": "2026-09-28",
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1q9ObChzWim0208z9idNpQpbHvr4IYOz5",
    "name": "2026-09-28 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "date": "2026-09-28",
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1_L5xoKcj0yMnDaLF3jSBleMApuVZWS1v",
    "name": "2026-09-30 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "date": "2026-09-30",
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1znsODtwdQz5Y_iMzLuKASvS6fxoC-okJ",
    "name": "2026-10-02 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-10-02",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1aKYivL6XK0X1MdTJI0gQDzzv_ztFiNUG",
    "name": "2026-10-05 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-10-05",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1oKG7V7F28hKamnrw64dBgvcukApcZVKr",
    "name": "2026-10-05 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "date": "2026-10-05",
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "1pNEHTd65SZDUz_AXqgycV1NLMxstpZCd",
    "name": "2026-10-06 - TA Session_ Pawan Sapkota - Recording.mp4",
    "date": "2026-10-06",
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1NpvqWSA0zeYW-Oh2xvJrhbU_6dypai9R",
    "name": "2026-10-08 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "date": "2026-10-08",
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1Vwk-BMwpBP8-rGTJFeLKlOP7Xh7_HDX8",
    "name": "2026-10-09 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-10-09",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1tzRg4Vx0KHpxMHlg3BUi2KFlSS1WNrqq",
    "name": "2026-10-09 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-10-09",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "196aheWwq19J2WfGAgyyN6JYO4H9XGRvL",
    "name": "2026-10-11 - TA Session_ Rakshya Lama Moktan - Recording.mp4",
    "date": "2026-10-11",
    "summary": "TA Session: Rakshya Lama Moktan"
  },
  {
    "id": "1GoTgtFMNv3GNMpU_jclc97PTTE1x5GXK",
    "name": "2026-10-11 - Week 18_ Responsible and TrusthWorthy AI - Recording.mp4",
    "date": "2026-10-11",
    "summary": "Week 18: Responsible and TrusthWorthy AI"
  },
  {
    "id": "1T2IJJ0giSLDQJO7nLwfwgNMKMHQZP7kS",
    "name": "2026-10-12 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-10-12",
    "summary": "TA Session: Bimarsha Khanal"
  },
  {
    "id": "1lFU2LshZUcgI74jOrCO8MKKXKMmrUJmY",
    "name": "2026-10-12 - TA Session_ Pawan Sapkota - Recording.mp4",
    "date": "2026-10-12",
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1R1gPZ0PY81RpS_58bXD0TvC6AOIgbFsW",
    "name": "2026-10-12 - TA Session_ Pawan Sapkota - Recording.mp4",
    "date": "2026-10-12",
    "summary": "TA Session: Pawan Sapkota"
  },
  {
    "id": "1cqQRbuVxNopFwqK3Cp783mpuouvh5ftE",
    "name": "2026-10-12 - TA Session_ Raj Kumar Biswokarma - Recording.mp4",
    "date": "2026-10-12",
    "summary": "TA Session: Raj Kumar Biswokarma"
  },
  {
    "id": "13fGoucBqyvbjvROT4rqhvIWBf9-WaHrP",
    "name": "2026-10-15 - TA Session_ Bimarsha Khanal - Recording.mp4",
    "date": "2026-10-15",
    "summary": "TA Session: Bimarsha Khanal"
  }
];
  
  Logger.log("Starting batch copy of " + files.length + " recordings directly inside Google Drive...");
  
  var successCount = 0;
  var skipCount = 0;
  var errorCount = 0;
  
  // Check existing files in folder to avoid duplicate copies if re-run
  var existingFileNames = {};
  var existingFilesIter = targetFolder.getFiles();
  while (existingFilesIter.hasNext()) {
    existingFileNames[existingFilesIter.next().getName()] = true;
  }
  
  for (var i = 0; i < files.length; i++) {
    var item = files[i];
    
    if (existingFileNames[item.name]) {
      Logger.log("[" + (i + 1) + "/" + files.length + "] Already exists, skipping: " + item.name);
      skipCount++;
      continue;
    }
    
    try {
      var sourceFile = DriveApp.getFileById(item.id);
      sourceFile.makeCopy(item.name, targetFolder);
      Logger.log("[" + (i + 1) + "/" + files.length + "] Successfully copied: " + item.name);
      successCount++;
      Utilities.sleep(400); // polite pause between copy operations
    } catch (e) {
      Logger.log("[" + (i + 1) + "/" + files.length + "] ERROR copying (" + item.id + ") " + item.name + ": " + e.message);
      errorCount++;
    }
  }
  
  Logger.log("=== COMPLETED ===");
  Logger.log("Successfully copied: " + successCount);
  Logger.log("Skipped (already present): " + skipCount);
  Logger.log("Errors / Restricted: " + errorCount);
}
