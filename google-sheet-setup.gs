/**
 * VoxSlide AI — Google Sheet form handler
 *
 * SETUP (one time, ~2 minutes):
 * 1. Open your sheet:
 *    https://docs.google.com/spreadsheets/d/1kHyHsEhiB7BGKjluj0oJGtacwjwo7NedBNJwxRwtRng/edit
 * 2. Extensions → Apps Script
 * 3. Delete any default code, paste ALL of this file, save (Ctrl+S)
 * 4. Deploy → New deployment → type: Web app
 *    - Execute as: Me
 *    - Who has access: Anyone
 * 5. Click Deploy, authorize when prompted, copy the Web app URL
 * 6. Paste that URL into index.html → SHEET_SCRIPT_URL
 *
 * If you already deployed: Deploy → Manage deployments → edit (pencil)
 * → New version → Deploy. Keep the same URL if possible.
 */

var SHEET_ID = '1kHyHsEhiB7BGKjluj0oJGtacwjwo7NedBNJwxRwtRng';

function getLeadSheet_() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  return ss.getSheetByName('Sheet1') || ss.getSheets()[0];
}

function readParams_(e) {
  var params = {};
  if (e && e.parameter) {
    params = e.parameter;
  }
  // Also accept JSON bodies (older frontend versions)
  try {
    if (e && e.postData && e.postData.contents) {
      var type = (e.postData.type || '').toLowerCase();
      if (type.indexOf('application/json') !== -1) {
        var parsed = JSON.parse(e.postData.contents);
        params = {
          fullName: parsed.fullName || params.fullName || '',
          email: parsed.email || params.email || '',
          whatsapp: parsed.whatsapp || params.whatsapp || ''
        };
      }
    }
  } catch (err) {}
  return params;
}

function doPost(e) {
  var params = readParams_(e);
  var sheet = getLeadSheet_();

  sheet.appendRow([
    new Date(),
    params.fullName || '',
    params.email || '',
    params.whatsapp || ''
  ]);

  return ContentService
    .createTextOutput(JSON.stringify({ success: true }))
    .setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  // Allows quick browser tests: ?fullName=Test&email=a@b.com&whatsapp=123
  if (e && e.parameter && (e.parameter.fullName || e.parameter.email || e.parameter.whatsapp)) {
    doPost(e);
    return ContentService
      .createTextOutput('Row added. Check your Google Sheet.')
      .setMimeType(ContentService.MimeType.TEXT);
  }
  return ContentService
    .createTextOutput('VoxSlide AI form endpoint is running.')
    .setMimeType(ContentService.MimeType.TEXT);
}
