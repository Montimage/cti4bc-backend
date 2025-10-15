/**
 * Web App entry point for GET requests
 * Expects formUrl parameter
 */
function doGet(e) {
  try {
    if (!e.parameter || !e.parameter.formUrl) {
      return ContentService.createTextOutput(JSON.stringify({
        error: "formUrl parameter is required"
      })).setMimeType(ContentService.MimeType.JSON);
    }
    
    var formUrl = e.parameter.formUrl;
    var result = getFormAsJsonByUrl(formUrl);
    
    return ContentService.createTextOutput(JSON.stringify(result))
                         .setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      error: "Error processing form: " + error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Web App entry point for POST requests
 * Expects formUrl in POST body
 */
function doPost(e) {
  try {
    var requestData = JSON.parse(e.postData.contents);
    if (!requestData.formUrl) {
      return ContentService.createTextOutput(JSON.stringify({
        error: "formUrl is required in request body"
      })).setMimeType(ContentService.MimeType.JSON);
    }
    
    var result = getFormAsJsonByUrl(requestData.formUrl);
    
    return ContentService.createTextOutput(JSON.stringify(result))
                         .setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      error: "Error processing form: " + error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Direct function callable via Apps Script API
 * Converts the given form URL into a JSON object.
 */
function getFormAsJsonByUrl(formUrl) {
  if (!formUrl) {
    throw new Error("Form URL is required");
  }
  
  try {
    // First, try to extract and validate the form ID
    var formId = extractFormId(formUrl);
    if (!formId) {
      throw new Error("Invalid Google Forms URL format. Please provide a valid Google Forms URL.");
    }
    
    // Try multiple URL formats to access the form
    var form = null;
    var lastError = null;
    
    // List of URL formats to try
    var urlsToTry = [
      formUrl, // Original URL
      "https://docs.google.com/forms/d/" + formId + "/edit", // Edit URL
      "https://docs.google.com/forms/d/" + formId + "/viewform", // View URL
      "https://docs.google.com/forms/d/" + formId // Basic URL
    ];
    
    for (var i = 0; i < urlsToTry.length; i++) {
      try {
        form = FormApp.openByUrl(urlsToTry[i]);
        if (form) {
          break; // Success!
        }
      } catch (error) {
        lastError = error;
        continue; // Try next URL format
      }
    }
    
    if (!form) {
      throw new Error("Unable to access the form. Please check: 1) The URL is correct, 2) The form exists, 3) You have permission to access it. Last error: " + (lastError ? lastError.toString() : "Unknown"));
    }
    
    var items = form.getItems();
    
    var result = {
      "metadata": getFormMetadata(form),
      "items": items.map(itemToObject),
      "count": items.length
    };
    
    return result;
    
  } catch (error) {
    // Re-throw with more context
    throw new Error("Failed to process form: " + error.toString());
  }
}

/**
 * Extract form ID from various Google Forms URL formats
 */
function extractFormId(url) {
  if (!url) return null;
  
  // Common Google Forms URL patterns
  var patterns = [
    /\/forms\/d\/([a-zA-Z0-9-_]+)/,
    /formResponse\?.*entry\.([0-9]+)/,
    /viewform\?.*id=([a-zA-Z0-9-_]+)/
  ];
  
  for (var i = 0; i < patterns.length; i++) {
    var match = url.match(patterns[i]);
    if (match && match[1]) {
      return match[1];
    }
  }
  
  return null;
}

/**
 * Legacy main function for testing
 * Note: This function is for testing purposes only.
 * In production, the form URL is always provided by the user via doGet() or doPost().
 */
function main() {
  // This function is kept for testing purposes but should not contain hardcoded URLs.
  // To test, manually call getFormAsJsonByUrl() with a valid form URL.
  Logger.log("Use getFormAsJsonByUrl(formUrl) with a valid form URL for testing.");
}

/**
 * Returns the form metadata object for the given Form object.
 * @param form: Form
 * @returns (Object) object of form metadata.
 */
function getFormMetadata(form) {
  return {
    "title": form.getTitle(),
    "id": form.getId(),
    "description": form.getDescription(),
    "publishedUrl": form.getPublishedUrl(),
    "editorEmails": form.getEditors().map(function(user) {return user.getEmail()}),
    "count": form.getItems().length,
    "confirmationMessage": form.getConfirmationMessage(),
    "customClosedFormMessage": form.getCustomClosedFormMessage()
  };
}

/**
 * Returns an Object for a given Item.
 * @param item: Item
 * @returns (Object) object for the given item.
 */
/**
 * Returns an Object for a given Item.
 * @param item: Item
 * @returns (Object) object for the given item.
 */
function itemToObject(item) {
  var data = {};
  
  data.type = item.getType().toString();
  data.title = item.getTitle();
  
  // Downcast items to access type-specific properties
  
  var itemTypeConstructorName = snakeCaseToCamelCase("AS_" + item.getType().toString() + "_ITEM");  
  var typedItem = item[itemTypeConstructorName]();
  
  // Keys with a prefix of "get" have "get" stripped
  
  var getKeysRaw = Object.keys(typedItem).filter(function(s) {return s.indexOf("get") == 0});
  
  getKeysRaw.map(function(getKey) {    
    var propName = getKey[3].toLowerCase() + getKey.substr(4);
    
    // Image data, choices, and type come in the form of objects / enums
    if (["image", "choices", "type", "alignment"].indexOf(propName) != -1) {return};
    
    // Skip feedback-related keys
    if (getKey === "getFeedbackForIncorrect" || getKey === "getFeedbackForCorrect"
      || getKey === "getGeneralFeedback") {return};
    
    var propValue = typedItem[getKey]();
    
    data[propName] = propValue;
  });
  
  // Bool keys are included as-is
  
  var boolKeys = Object.keys(typedItem).filter(function(s) {
    return (s.indexOf("is") == 0) || (s.indexOf("has") == 0) || (s.indexOf("includes") == 0);
  });
  
  boolKeys.map(function(boolKey) {
    var propName = boolKey;
    var propValue = typedItem[boolKey]();
    data[propName] = propValue;
  });
  
  // Handle image data and list choices
  
  switch (item.getType()) {
    case FormApp.ItemType.LIST:
    case FormApp.ItemType.CHECKBOX:
    case FormApp.ItemType.MULTIPLE_CHOICE:
      data.choices = typedItem.getChoices().map(function(choice) {
        return choice.getValue();
      });
      break;
    
    case FormApp.ItemType.IMAGE:
      data.alignment = typedItem.getAlignment().toString();
      
      if (item.getType() == FormApp.ItemType.VIDEO) { // This condition might be redundant or misplaced as VIDEO is handled later
        return;
      }
      
      var imageBlob = typedItem.getImage();
      
      data.imageBlob = {
        "dataAsString": imageBlob.getDataAsString(),
        "name": imageBlob.getName(),
        "isGoogleType": imageBlob.isGoogleType()
      };
      
      break;
      
    case FormApp.ItemType.PAGE_BREAK:
      data.pageNavigationType = typedItem.getPageNavigationType().toString();
      break;
      
    default:
      break;
  }
  
  // Have to do this because for some reason Google Scripts API doesn't have a
  // native VIDEO type
  if (item.getType().toString() === "VIDEO") {
    data.alignment = typedItem.getAlignment().toString();
  }
  
  return data;
}

/**
 * Converts a SNAKE_CASE string to a camelCase string.
 * @param s: string in snake_case
 * @returns (string) the camelCase version of that string
 */
function snakeCaseToCamelCase(s) {
  return s.toLowerCase().replace(/(\_\w)/g, function(m) {return m[1].toUpperCase();});
}