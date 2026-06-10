function createFieldRequiredValidator() {
  return {
    trigger: "change",
    validators: {
      notEmpty: {
        message: "This field is required",
      },
      regexp: {
        regexp: /\S/,
        message: "This field is required",
      },
    },
  };
}

function createFieldRequiredValidatorWithMaxLength(maxLength) {
  const baseValidator = createFieldRequiredValidator();
  baseValidator.validators.stringLength = {
    max: maxLength,
    message: `This field must not exceed ${maxLength} characters.`,
  };
  return baseValidator;
}

function createAlphabetsRequiredValidator() {
  const baseValidator = createFieldRequiredValidator();
  baseValidator.validators.regexp = {
    regexp: /^(?=.*\S)[a-zA-Z\s]+$/,
    message: "This field must be alphabets",
  };
  return baseValidator;
}

function createAlphabetsRequiredValidatorWithMaxLength(maxLength) {
  const baseValidator = createAlphabetsRequiredValidator();
  baseValidator.validators.stringLength = {
    max: maxLength,
    message: `This field must not exceed ${maxLength} characters.`,
  };
  return baseValidator;
}

function createAlphaNumericRequiredValidator() {
  const baseValidator = createFieldRequiredValidator();
  baseValidator.validators.regexp = {
    regexp: /^(?=.*\S)[a-zA-Z0-9\s]+$/,
    message: "This field must be alphanumeric",
  };
  return baseValidator;
}

function createAlphaNumericRequiredValidatorWithMaxLength(maxLength) {
  const baseValidator = createAlphaNumericRequiredValidator();
  baseValidator.validators.stringLength = {
    max: maxLength,
    message: `This field must not exceed ${maxLength} characters.`,
  };
  return baseValidator;
}

function createAlphaNumericRequiredWithoutSpaceValidator() {
  const baseValidator = createFieldRequiredValidator();
  baseValidator.validators.regexp = {
    regexp: /^[a-zA-Z0-9]*$/,
    message: "This field must be alphanumeric without whitespace(s)",
  };
  return baseValidator;
}

function createEmailValidator() {
  return {
    validators: {
      regexp: {
        regexp: /^[a-zA-Z0-9._%+-]+@(?!(?:.*\.\.)|(?:.*\.$))[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,
        message: "Please enter a valid email address",
      },
    },
  };
}

function createOptionalDescriptionValidatorWithMaxLength(maxLength) {
  return {
    validators: {
      callback: {
        message: `This field must not exceed ${maxLength} characters.`,
        callback: function (input) {
          return (
            input.value.trim() === "" || input.value.trim().length <= maxLength
          );
        },
      },
    },
  };
}
