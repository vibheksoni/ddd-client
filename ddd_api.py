import base64
import csv
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

import bs4
import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ddd_api.log")
    ]
)
logger = logging.getLogger("ddd_api")

def parse_jwt_token(jwt_token: str) -> Dict[str, Any]:
    """
    Parse a JWT token and extract its payload.

    Args:
        jwt_token (str): The JWT token string to parse.

    Returns:
        Dict[str, Any]: A dictionary containing the token payload.
                        Returns an empty dictionary if parsing fails or the token is invalid.
    """
    try:
        parts = jwt_token.split('.')
        if len(parts) != 3:
            logger.warning(f"Invalid JWT token format: {jwt_token[:10]}...")
            return {}

        payload_b64 = parts[1]
        padding_needed = len(payload_b64) % 4
        if padding_needed:
            payload_b64 += '=' * (4 - padding_needed)

        payload_b64 = payload_b64.replace('-', '+').replace('_', '/')

        try:
            payload_json = base64.b64decode(payload_b64).decode('utf-8')
            payload = json.loads(payload_json)
            return payload
        except Exception as e:
            logger.warning(f"Error decoding JWT payload: {e}")
            return {}
    except Exception as e:
        logger.warning(f"Error parsing JWT token: {e}")
        return {}

class DDDGermanAPIError(Exception):
    """Base class for exceptions in this module."""
    pass

class APIConnectionError(DDDGermanAPIError):
    """Raised for errors during connection to the API."""
    pass

class AuthenticationError(DDDGermanAPIError):
    """Raised for authentication failures (e.g., invalid JWT)."""
    pass

class NotFoundError(DDDGermanAPIError):
    """Raised when a resource is not found (404)."""
    pass

class BadRequestError(DDDGermanAPIError):
    """Raised for bad requests (400), e.g., invalid payload."""
    pass

class ForbiddenError(DDDGermanAPIError):
    """Raised when access is forbidden (403)."""
    pass

class ServerError(DDDGermanAPIError):
    """Raised for server-side errors (500+)."""
    pass

class FormParsingError(DDDGermanAPIError):
    """Raised when there's an error parsing form data from HTML content."""
    pass

class FormSubmissionError(DDDGermanAPIError):
    """Raised when there's an error submitting a form response."""
    pass

class FormValidationError(DDDGermanAPIError):
    """Raised when form data validation fails."""
    pass

class FormFieldType(Enum):
    """
    Enumeration for different types of form fields encountered in HTML forms.
    """
    TEXT = auto()
    TEXTAREA = auto()
    RADIO = auto()
    CHECKBOX = auto()
    SELECT = auto()
    UNKNOWN = auto()

@dataclass
class FormField:
    """
    Represents a single field within an HTML form.

    Attributes:
        name (str): The name attribute of the form field.
        field_type (FormFieldType): The type of the form field (e.g., TEXT, RADIO).
        label (Optional[str]): The human-readable label associated with the field.
        options (List[Dict[str, str]]): A list of options for fields like SELECT, RADIO, CHECKBOX.
                                         Each option is a dictionary with 'value' and 'label'.
        value (Optional[str]): The current value of the form field.
        required (bool): Whether the form field is marked as required.
    """
    name: str
    field_type: FormFieldType
    label: Optional[str] = None
    options: List[Dict[str, str]] = field(default_factory=list)
    value: Optional[str] = None
    required: bool = False

    def __repr__(self) -> str:
        """
        Provides a string representation of the FormField object.

        Returns:
            str: A string representation of the form field.
        """
        return f"<FormField name='{self.name}' type={self.field_type.name} value='{self.value}'>"

@dataclass
class FormData:
    """
    Represents the entire data structure of an HTML form, including its ID and all its fields.

    Attributes:
        form_id (str): The ID attribute of the form.
        fields (List[FormField]): A list of FormField objects representing the fields in this form.
        question_text (Optional[str]): Text extracted from the HTML that might represent
                                       the question or instruction associated with the form.
    """
    form_id: str
    fields: List[FormField] = field(default_factory=list)
    question_text: Optional[str] = None

    def to_dict(self) -> Dict[str, str]:
        """
        Converts the form data into a dictionary suitable for submission.
        Only fields with a non-None value are included.

        Returns:
            Dict[str, str]: A dictionary mapping field names to their values.
        """
        return {field.name: field.value for field in self.fields if field.value is not None}

    def from_dict(self, data: Dict[str, str]) -> None:
        """
        Populates the form fields' values from a dictionary.

        Args:
            data (Dict[str, str]): A dictionary mapping field names to their intended values.
        """
        for field_obj in self.fields:
            if field_obj.name in data:
                field_obj.value = data[field_obj.name]

    def __repr__(self) -> str:
        """
        Provides a string representation of the FormData object.

        Returns:
            str: A string representation of the form data.
        """
        return f"<FormData form_id='{self.form_id}' fields={len(self.fields)}>"

class FormParser:
    """
    A utility class for parsing HTML content to extract and interpret form structures.
    It uses BeautifulSoup to navigate and analyze the HTML DOM.
    """

    @staticmethod
    def extract_forms(html_content: str) -> List[Tuple[str, str]]:
        """
        Extracts all <form> elements or form-like structures from HTML content.

        This method employs several strategies to find forms, including looking for
        <form> tags with IDs, <form> tags without IDs (generating synthetic IDs),
        and <div> elements that appear to contain form inputs if no explicit <form>
        tags are found. It prioritizes forms with IDs and includes the parent <div>
        to capture contextual information.

        Args:
            html_content (str): The HTML content to parse.

        Returns:
            List[Tuple[str, str]]: A list of tuples, where each tuple contains
                                   (form_id, form_html_string).

        Raises:
            FormParsingError: If there's an underlying error during BeautifulSoup parsing
                              or if the HTML structure is unexpectedly malformed.
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            forms = []

            for form_element in soup.find_all('form'):
                form_id = form_element.get('id')
                if form_id:
                    parent_div = form_element.find_parent('div')
                    forms.append((form_id, str(parent_div) if parent_div else str(form_element)))

            if not forms:
                for i, form_element in enumerate(soup.find_all('form')):
                    form_id = f"form-{i+1}"
                    parent_div = form_element.find_parent('div')
                    forms.append((form_id, str(parent_div) if parent_div else str(form_element)))

            if not forms:
                form_like_divs = soup.find_all(
                    'div',
                    class_=lambda c: c and ('form' in c.lower() or 'input' in c.lower() or 'question' in c.lower())
                )
                for i, div in enumerate(form_like_divs):
                    if div.find(['input', 'textarea', 'select']):
                        form_id = f"synthetic-form-{i+1}"
                        forms.append((form_id, str(div)))

            if not forms:
                for i, div in enumerate(soup.find_all('div')):
                    if div.find(['input', 'textarea', 'select']):
                        form_id = f"div-form-{i+1}"
                        forms.append((form_id, str(div)))

            logger.info(f"Found {len(forms)} forms in HTML content")
            return forms
        except Exception as e:
            logger.error(f"Error extracting forms from HTML: {e}")
            raise FormParsingError(f"Failed to extract forms from HTML: {e}")

    @staticmethod
    def parse_form(form_html: str) -> FormData:
        """
        Parses a single HTML form string and extracts its fields and structure.

        It identifies various input types (text, textarea, radio, checkbox, select)
        and attempts to find associated labels and options.

        Args:
            form_html (str): The HTML string representing a single form or form-like structure.

        Returns:
            FormData: A FormData object populated with the parsed form's details.

        Raises:
            FormParsingError: If no <form> tag is found within the provided HTML
                              or if a critical parsing error occurs.
        """
        try:
            soup = BeautifulSoup(form_html, 'html.parser')
            form_element = soup.find('form')

            if not form_element:
                # If no <form> tag, treat the whole soup as the form context (for synthetic forms)
                form_element = soup

            form_id = form_element.get('id', '') if form_element.name == 'form' else form_html_hash(form_html) # Simplified ID generation
            form_data = FormData(form_id=form_id)
            form_data.question_text = FormParser._extract_question_text(form_element)

            for input_elem in form_element.find_all('input'):
                input_type = input_elem.get('type', 'text').lower()
                name = input_elem.get('name')
                if not name:
                    continue

                if input_type in ['text', 'password', 'email', 'number', 'hidden', 'submit', 'button', 'reset', 'file', 'image', 'search', 'tel', 'url', 'date', 'datetime-local', 'month', 'week', 'time', 'color']:
                    field = FormField(
                        name=name,
                        field_type=FormFieldType.TEXT, # Generalize for simplicity or extend Enum
                        label=FormParser._find_label(form_element, name, input_elem.get('id')),
                        value=input_elem.get('value'),
                        required=input_elem.get('required') is not None
                    )
                    form_data.fields.append(field)
                elif input_type in ['radio', 'checkbox']:
                    existing_field = next((f for f in form_data.fields if f.name == name), None)
                    value = input_elem.get('value', '')
                    option_label_id = input_elem.get('id')
                    option_label = FormParser._find_label(form_element, name, option_label_id, value_attr=value)

                    if existing_field:
                        existing_field.options.append({'value': value, 'label': option_label or value})
                    else:
                        field_type = FormFieldType.RADIO if input_type == 'radio' else FormFieldType.CHECKBOX
                        field = FormField(
                            name=name,
                            field_type=field_type,
                            label=FormParser._find_label(form_element, name, input_elem.get('id')), # Group label
                            required=input_elem.get('required') is not None
                        )
                        field.options.append({'value': value, 'label': option_label or value})
                        form_data.fields.append(field)

            for textarea in form_element.find_all('textarea'):
                name = textarea.get('name')
                if name:
                    field = FormField(
                        name=name,
                        field_type=FormFieldType.TEXTAREA,
                        label=FormParser._find_label(form_element, name, textarea.get('id')),
                        value=textarea.get_text(),
                        required=textarea.get('required') is not None
                    )
                    form_data.fields.append(field)

            for select in form_element.find_all('select'):
                name = select.get('name')
                if name:
                    field = FormField(
                        name=name,
                        field_type=FormFieldType.SELECT,
                        label=FormParser._find_label(form_element, name, select.get('id')),
                        required=select.get('required') is not None
                    )
                    for option in select.find_all('option'):
                        value = option.get('value', option.get_text(strip=True))
                        label = option.get_text(strip=True)
                        field.options.append({'value': value, 'label': label})
                        if option.get('selected') is not None:
                             field.value = value
                    form_data.fields.append(field)
            return form_data
        except Exception as e:
            logger.error(f"Error parsing form: {e}")
            raise FormParsingError(f"Failed to parse form: {e}")

    @staticmethod
    def _extract_question_text(form_element: bs4.Tag) -> str:
        """
        Extracts potential question text associated with a form element.

        This method uses a series of strategies to find text that could serve as
        the question or instruction for the form. Strategies include looking for
        specific CSS classes used by the DDD German platform (e.g., 'rs-exercise-prompt'),
        searching for text in parent elements, preceding sibling elements (like <p> or <h1>-<h6>),
        <legend> tags, and text within elements having classes like 'form-group'.
        It also tries to find text containing German question words or question marks.
        As a last resort, it may construct a pseudo-question from field labels or placeholders.

        Args:
            form_element (bs4.Tag): The BeautifulSoup Tag object representing the form
                                    or a form-like container.

        Returns:
            str: The extracted question text, or an empty string if no suitable text is found.
        """
        question_text = ""
        strategies: List[Callable[[bs4.Tag], Optional[str]]] = [
            lambda el: next((p.get_text(strip=True) for p in el.find_all('div', class_='rs-exercise-prompt') if p.get_text(strip=True)), None),
            lambda el: next((p.get_text(strip=True) for p in el.find_all('div', class_='rs-exercise-instruction') if p.get_text(strip=True)), None),
            lambda el: next((p.get_text(strip=True) for p in el.find_all('div', class_='rs-exercise-question') if p.get_text(strip=True)), None),
            lambda el: next((div.get_text(strip=True) for div in el.find_all('div', class_=lambda c: c and 'exercise' in c.lower()) if div.find('form') != el and 5 < len(div.get_text(strip=True)) < 500), None),
        ]

        for strategy in strategies:
            text = strategy(form_element)
            if text: return text

        parent_div = form_element.find_parent('div')
        if parent_div:
            question_divs = parent_div.find_all(['div', 'p'], class_=lambda c: c and ('question' in c.lower() or 'prompt' in c.lower() or 'instruction' in c.lower()))
            if question_divs:
                return question_divs[0].get_text(strip=True)

        prev_elems = form_element.find_all_previous(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div'], limit=5)
        for elem in prev_elems:
            text = elem.get_text(strip=True)
            if text and 5 < len(text) < 500:
                return text

        legend = form_element.find('legend')
        if legend: return legend.get_text(strip=True)

        form_groups = form_element.find_all('div', class_=lambda c: c and ('form-group' in c.lower() or 'field-group' in c.lower()))
        for group in form_groups:
            labels = group.find_all(['label', 'h3', 'h4', 'p'])
            if labels: return labels[0].get_text(strip=True)

        if form_element.parent and form_element.parent.name not in ['body', 'html']:
            for child in form_element.parent.children:
                if isinstance(child, str) and child.strip():
                    return child.strip()

        form_title = form_element.get('title') or form_element.get('aria-label')
        if form_title: return form_title

        slide_content = form_element.find_parent(['div', 'section'])
        if slide_content:
            paragraphs = slide_content.find_all(['p', 'div'], class_=lambda c: not c or 'question' in str(c).lower())
            for p_elem in paragraphs:
                text = p_elem.get_text(strip=True)
                if text and '?' in text and len(text) < 500: return text

            german_question_words = ['wer', 'was', 'wo', 'wann', 'warum', 'wie', 'welche', 'welcher', 'welches', 'wohin', 'woher']
            for text_node in slide_content.find_all(string=True):
                text_lower = text_node.lower()
                if any(word in text_lower for word in german_question_words) and 10 < len(text_node) < 500:
                    return text_node.strip()

        if not question_text:
            field_labels = [label.get_text(strip=True) for label in form_element.find_all('label') if label.get_text(strip=True) and len(label.get_text(strip=True)) > 3]
            if field_labels:
                question_text = " / ".join(field_labels[:3])
                if len(field_labels) > 3: question_text += " ..."
                return question_text
            else:
                inputs = form_element.find_all('input')
                for input_elem in inputs:
                    placeholder = input_elem.get('placeholder')
                    if placeholder and len(placeholder) > 3: return f"Input: {placeholder}"

        if not question_text and form_element.name == 'form' and form_element.get('id'):
            return f"Exercise {form_element.get('id')}"

        return question_text

    @staticmethod
    def _find_label(form_element: bs4.Tag, field_name: str, field_id: Optional[str] = None, value_attr: Optional[str] = None) -> Optional[str]:
        """
        Finds the label text for a given form field.

        It tries several methods:
        1. Look for a <label> tag with a 'for' attribute matching the field's ID.
        2. If `field_id` is for a radio/checkbox option, look for a label next to or parent of the specific input.
        3. Look for a <label> tag with a 'for' attribute matching the field's name (less common).
        4. If the input is wrapped by a <label> tag, return the text of that label.

        Args:
            form_element (bs4.Tag): The BeautifulSoup Tag object for the form or form container.
            field_name (str): The 'name' attribute of the form field.
            field_id (Optional[str]): The 'id' attribute of the form field.
            value_attr (Optional[str]): The 'value' attribute, used for radio/checkbox options
                                        to help locate specific labels.

        Returns:
            Optional[str]: The text of the found label, or None if no label is found.
        """
        if field_id:
            label = form_element.find('label', {'for': field_id})
            if label:
                return label.get_text(strip=True)

        # For radio/checkbox, the label might be associated with the specific value
        if value_attr is not None:
            # Try to find input by name and value, then its associated label
            inputs_with_value = form_element.find_all('input', {'name': field_name, 'value': value_attr})
            for input_elem_val in inputs_with_value:
                # Check label with 'for' matching this specific input's id
                if input_elem_val.get('id'):
                    label_for_specific_id = form_element.find('label', {'for': input_elem_val.get('id')})
                    if label_for_specific_id: return label_for_specific_id.get_text(strip=True)

                # Check for a label immediately following this input
                next_elem = input_elem_val.find_next_sibling()
                if next_elem and next_elem.name == 'label':
                    return next_elem.get_text(strip=True)
                # Check for a label containing this input
                parent_label = input_elem_val.find_parent('label')
                if parent_label:
                    # Attempt to get text that is not the input itself if nested
                    cloned_label = BeautifulSoup(str(parent_label), 'html.parser').label
                    if cloned_label:
                        nested_input = cloned_label.find('input', {'name': field_name, 'value': value_attr})
                        if nested_input:
                            nested_input.decompose() # Remove the input to get only label text
                        return cloned_label.get_text(strip=True)
                    return parent_label.get_text(strip=True) # Fallback

        # Fallback: Try to find a label with 'for' attribute matching the field name (less common but possible)
        label_for_name = form_element.find('label', {'for': field_name})
        if label_for_name:
            return label_for_name.get_text(strip=True)

        # Fallback: If no specific label, find the input and see if its parent is a label (common for radio/checkbox)
        # This is partially covered above, but as a general fallback for other inputs:
        target_input = form_element.find('input', {'name': field_name, 'id': field_id}) or form_element.find('input', {'name': field_name})
        if target_input and target_input.parent and target_input.parent.name == 'label':
            return target_input.parent.get_text(strip=True)

        return None

def form_html_hash(form_html: str) -> str:
    """Generates a simple hash for form HTML to be used as a synthetic ID."""
    import hashlib
    return "synthetic-" + hashlib.md5(form_html.encode('utf-8')).hexdigest()[:8]


class Chapter:
    """
    Represents a chapter (Kapitel) in the DDD German learning platform.

    Attributes:
        id (int): The unique identifier for the chapter.
        name (str): The name of the chapter.
        quizlet_embed_code (Optional[str]): Embed code for Quizlet, if available.
        _client (DDDGermanPlatform): An instance of the API client for making requests.
        _themes (Optional[List[Theme]]): A cached list of themes belonging to this chapter.
    """
    def __init__(self, platform_client: 'DDDGermanPlatform', kapitel_id: int, name: str, quizlet_embed_code: Optional[str]):
        """
        Initializes a Chapter object.

        Args:
            platform_client (DDDGermanPlatform): The API client instance.
            kapitel_id (int): The ID of the chapter.
            name (str): The name of the chapter.
            quizlet_embed_code (Optional[str]): Quizlet embed code, if any.
        """
        self._client = platform_client
        self.id = kapitel_id
        self.name = name
        self.quizlet_embed_code = quizlet_embed_code
        self._themes: Optional[List['Theme']] = None

    def __repr__(self) -> str:
        """
        Provides a string representation of the Chapter object.

        Returns:
            str: A string representation like "<Chapter id=1 name='Chapter Name'>".
        """
        return f"<Chapter id={self.id} name='{self.name}'>"

    def get_themes(self) -> List['Theme']:
        """
        Retrieves all themes (Themas) associated with this chapter.

        Themes are filtered from a globally fetched list of all themes if not already cached.

        Returns:
            List[Theme]: A list of Theme objects belonging to this chapter.
        """
        if self._themes is None:
            all_themas_data = self._client._fetch_all_themas_data()
            self._themes = []
            for thema_data in all_themas_data:
                if isinstance(thema_data, dict) and thema_data.get('kapitel') == self.id:
                    self._themes.append(
                        Theme(
                            platform_client=self._client,
                            kapitel_id=thema_data['kapitel'],
                            thema_id=thema_data['thema'],
                            name=thema_data.get('name', 'Unnamed Theme'),
                            render_vocab=thema_data.get('renderVocab', False),
                            quizlet_embed_code=thema_data.get('quizletEmbedCode')
                        )
                    )
                elif not isinstance(thema_data, dict):
                    logger.warning(f"Warning: Expected dict for thema_data in chapter {self.id}, got {type(thema_data)}: {thema_data}")
        return self._themes

    def get_theme_by_id(self, thema_id: int) -> Optional['Theme']:
        """
        Retrieves a specific theme by its ID within this chapter.

        Args:
            thema_id (int): The ID of the theme to retrieve.

        Returns:
            Optional[Theme]: The Theme object if found, otherwise None.
        """
        themes = self.get_themes()
        for theme in themes:
            if theme.id == thema_id:
                return theme
        return None

    def get_vocabulary(self) -> List['VocabularyItem']:
        """
        Retrieves all vocabulary items for this chapter.

        Handles variations in API response key names (e.g., 'german' vs 'word').

        Returns:
            List[VocabularyItem]: A list of VocabularyItem objects for this chapter.
        """
        endpoint = f"vocab/{self.id}"
        vocab_data = self._client._make_request("GET", endpoint, authenticated=True)
        valid_vocab_items = []
        if vocab_data and isinstance(vocab_data, list):
            for item_data in vocab_data:
                if isinstance(item_data, dict):
                    german_word = item_data.get('german', item_data.get('word'))
                    english_translation = item_data.get('english', item_data.get('translation'))
                    item_id = item_data.get('id')
                    kapitel_id = item_data.get('kapitel', self.id)
                    thema_id = item_data.get('thema')

                    if item_id is not None and german_word is not None and english_translation is not None:
                        valid_vocab_items.append(VocabularyItem(
                            platform_client=self._client,
                            id=item_id,
                            kapitel=kapitel_id,
                            thema=thema_id,
                            german=german_word,
                            english=english_translation,
                            **{k: v for k, v in item_data.items() if k not in ['id', 'kapitel', 'thema', 'german', 'english', 'word', 'translation']}
                        ))
                    else:
                        missing_keys = [k for k, v in [("'id'", item_id), ("'german' or 'word'", german_word), ("'english' or 'translation'", english_translation)] if v is None]
                        logger.warning(f"Chapter vocabulary item skipped. Missing keys: {', '.join(missing_keys)}. Data: {item_data}")
                else:
                    logger.warning(f"Warning: Expected dict for chapter vocabulary item, got {type(item_data)}: {item_data}")
        return valid_vocab_items

class Theme:
    """
    Represents a theme or section (Thema) within a chapter.

    Attributes:
        kapitel_id (int): The ID of the chapter this theme belongs to.
        id (int): The unique identifier for the theme.
        name (str): The name of the theme.
        render_vocab (bool): A flag indicating if vocabulary should be rendered for this theme.
        quizlet_embed_code (Optional[str]): Embed code for Quizlet, if available for this theme.
        _client (DDDGermanPlatform): An instance of the API client.
    """
    def __init__(self, platform_client: 'DDDGermanPlatform', kapitel_id: int, thema_id: int, name: str, render_vocab: bool, quizlet_embed_code: Optional[str]):
        """
        Initializes a Theme object.

        Args:
            platform_client (DDDGermanPlatform): The API client instance.
            kapitel_id (int): The ID of the parent chapter.
            thema_id (int): The ID of the theme.
            name (str): The name of the theme.
            render_vocab (bool): Whether vocabulary is typically rendered.
            quizlet_embed_code (Optional[str]): Quizlet embed code, if any.
        """
        self._client = platform_client
        self.kapitel_id = kapitel_id
        self.id = thema_id
        self.name = name
        self.render_vocab = render_vocab
        self.quizlet_embed_code = quizlet_embed_code

    def __repr__(self) -> str:
        """
        Provides a string representation of the Theme object.

        Returns:
            str: A string representation like "<Theme kapitel=1 thema=1 name='Theme Name'>".
        """
        return f"<Theme kapitel={self.kapitel_id} thema={self.id} name='{self.name}'>"

    @property
    def chapter_id(self) -> int:
        """int: The ID of the chapter this theme belongs to."""
        return self.kapitel_id

    @property
    def theme_id(self) -> int:
        """int: The ID of this theme."""
        return self.id

    def get_slides(self, include_all_institutions: bool = False) -> List['Slide']:
        """
        Retrieves all slides associated with this theme.

        Requires authentication. Handles potentially missing 'title' or 'institutionId'
        in the API response by providing defaults.

        Args:
            include_all_institutions (bool): Flag to include slides from all institutions. Defaults to False.

        Returns:
            List[Slide]: A list of Slide objects for this theme.
        """
        endpoint = f"slides/{self.kapitel_id}/{self.id}?includeAllInstitutions={str(include_all_institutions).lower()}"
        slides_data = self._client._make_request("GET", endpoint, authenticated=True)
        valid_slides = []
        if isinstance(slides_data, list):
            for slide_data in slides_data:
                if isinstance(slide_data, dict):
                    slide_id = slide_data.get('id')
                    if slide_id is not None:
                        valid_slides.append(Slide(
                            platform_client=self._client,
                            id=slide_id,
                            kapitel=slide_data.get('kapitel', self.kapitel_id),
                            thema=slide_data.get('thema', self.id),
                            title=slide_data.get('title', 'Untitled Slide'),
                            content=slide_data.get('content', ''),
                            institutionId=slide_data.get('institutionId'),
                            **{k: v for k, v in slide_data.items() if k not in ['id', 'kapitel', 'thema', 'title', 'content', 'institutionId']}
                        ))
                    else:
                        logger.warning(f"Warning: Slide item skipped due to missing 'id'. Data: {slide_data}")
                else:
                    logger.warning(f"Warning: Expected dict for slide item, got {type(slide_data)}: {slide_data}")
        return valid_slides

    def get_slide_orders(self) -> List['SlideOrder']:
        """
        Retrieves the order of slides for this theme.

        Requires authentication.

        Returns:
            List[SlideOrder]: A list of SlideOrder objects defining the sequence of slides.
        """
        endpoint = f"slideOrders/{self.kapitel_id}/{self.id}"
        orders_data = self._client._make_request("GET", endpoint, authenticated=True)
        if isinstance(orders_data, list):
            return [
                SlideOrder(self._client, **order) for order in orders_data
                if isinstance(order, dict) and 'id' in order and 'slideId' in order and 'order' in order
            ]
        return []

    def get_vocabulary(self) -> List['VocabularyItem']:
        """
        Retrieves vocabulary items specific to this theme.

        Requires authentication. Handles variations in API key names.

        Returns:
            List[VocabularyItem]: A list of VocabularyItem objects for this theme.
        """
        endpoint = f"vocab/{self.kapitel_id}/{self.id}"
        vocab_data = self._client._make_request("GET", endpoint, authenticated=True)
        valid_vocab_items = []
        if vocab_data and isinstance(vocab_data, list):
            for item_data in vocab_data:
                if isinstance(item_data, dict):
                    german_word = item_data.get('german', item_data.get('word'))
                    english_translation = item_data.get('english', item_data.get('translation'))
                    item_id = item_data.get('id')

                    if item_id is not None and german_word is not None and english_translation is not None:
                        valid_vocab_items.append(VocabularyItem(
                            platform_client=self._client,
                            id=item_id,
                            kapitel=item_data.get('kapitel', self.kapitel_id),
                            thema=item_data.get('thema', self.id),
                            german=german_word,
                            english=english_translation,
                            **{k: v for k, v in item_data.items() if k not in ['id', 'kapitel', 'thema', 'german', 'english', 'word', 'translation']}
                        ))
                    else:
                        missing_keys = [k for k, v in [("'id'", item_id), ("'german' or 'word'", german_word), ("'english' or 'translation'", english_translation)] if v is None]
                        logger.warning(f"Theme vocabulary item skipped. Missing keys: {', '.join(missing_keys)}. Data: {item_data}")
                else:
                    logger.warning(f"Warning: Expected dict for theme vocabulary item, got {type(item_data)}: {item_data}")
        return valid_vocab_items

    def get_user_responses(self, user_id: int) -> List['UserResponse']:
        """
        Retrieves responses submitted by a specific user for this theme.

        Requires authentication. Uses query parameters to filter responses by user,
        chapter (kapitel), and theme (thema).

        Args:
            user_id (int): The ID of the user whose responses are to be fetched.

        Returns:
            List[UserResponse]: A list of UserResponse objects.
        """
        endpoint = "responses"
        params = {
            "userId": user_id,
            "kapitel": self.kapitel_id,
            "thema": self.id
        }
        logger.info(f"Getting responses for user {user_id} in theme {self.kapitel_id}/{self.id}")
        responses_data = self._client._make_request("GET", endpoint, params=params, authenticated=True)
        valid_responses = []

        if isinstance(responses_data, list):
            logger.info(f"Found {len(responses_data)} responses for theme {self.kapitel_id}_{self.id}")
            for response in responses_data:
                if isinstance(response, dict):
                    try:
                        converted_data = {
                            "id": response.get("id", -1),
                            "userId": response.get("userId"),
                            "kapitel": response.get("kapitel"),
                            "thema": response.get("thema"),
                            "slideId": response.get("slideId"),
                            "formId": response.get("formId"),
                            "formData": response.get("formData"),
                            "response": response.get("response"), # Keep for backward compatibility
                            "createdAt": response.get("dateCreated", response.get("createdAt")),
                            "updatedAt": response.get("dateModified", response.get("updatedAt"))
                        }
                        # Add any other fields
                        for key, value in response.items():
                            if key not in converted_data and key not in ["dateCreated", "dateModified"]:
                                converted_data[key] = value
                        valid_responses.append(UserResponse(self._client, **converted_data))
                    except Exception as e:
                        logger.error(f"Warning: Failed to process response data: {e}. Data: {response}")
        return valid_responses

    def create_form(self, user_id: int, form_id: str, slide_id: int) -> 'Form':
        """
        Creates a Form handler instance for submitting responses to a specific form
        on a slide within this theme.

        Args:
            user_id (int): The ID of the user submitting the form.
            form_id (str): The ID of the form.
            slide_id (int): The ID of the slide containing the form.

        Returns:
            Form: A Form object configured for the specified context.
        """
        return Form(
            platform_client=self._client,
            user_id=user_id,
            kapitel_id=self.kapitel_id,
            thema_id=self.id,
            form_id=form_id,
            slide_id=slide_id
        )

class Slide:
    """
    Represents a single content slide within a theme.

    A slide contains HTML content which may include text, images, and interactive forms.

    Attributes:
        id (int): The unique identifier for the slide.
        kapitel_id (int): The ID of the chapter this slide belongs to.
        thema_id (int): The ID of the theme this slide belongs to.
        title (str): The title of the slide. Defaults to "Untitled Slide".
        content_html (str): The HTML content of the slide. Defaults to an empty string.
        institution_id (Optional[int]): The ID of the institution this slide is associated with, if any.
        additional_attributes (Dict[str, Any]): A dictionary holding any other attributes
                                                returned by the API for this slide.
        _client (DDDGermanPlatform): An instance of the API client.
        _forms (Optional[List[FormData]]): Cached list of parsed forms from the slide's content.
        _form_ids (Optional[List[str]]): Cached list of form IDs found on the slide.
        _extracted_text (Optional[str]): Cached plain text extracted from HTML content.
        _potential_questions (Optional[List[str]]): Cached list of potential questions from content.
    """
    def __init__(self, platform_client: 'DDDGermanPlatform', id: int, kapitel: int, thema: int, title: Optional[str], content: Optional[str], institutionId: Optional[int], **kwargs):
        """
        Initializes a Slide object.

        Args:
            platform_client (DDDGermanPlatform): The API client instance.
            id (int): The slide's unique ID.
            kapitel (int): The parent chapter's ID.
            thema (int): The parent theme's ID.
            title (Optional[str]): The title of the slide.
            content (Optional[str]): The HTML content of the slide.
            institutionId (Optional[int]): The institution ID, if applicable.
            **kwargs: Additional attributes from the API response.
        """
        self._client = platform_client
        self.id = id
        self.kapitel_id = kapitel
        self.thema_id = thema
        self.title = title if title is not None else "Untitled Slide"
        self.content_html = content if content is not None else ""
        self.institution_id = institutionId
        self.additional_attributes = kwargs
        self._forms: Optional[List[FormData]] = None
        self._form_ids: Optional[List[str]] = None
        self._extracted_text: Optional[str] = None
        self._potential_questions: Optional[List[str]] = None

    def __repr__(self) -> str:
        """
        Provides a string representation of the Slide object.

        Returns:
            str: A string representation like "<Slide id=101 title='Slide Title' kapitel=1 thema=1>".
        """
        return f"<Slide id={self.id} title='{self.title}' kapitel={self.kapitel_id} thema={self.thema_id}>"

    def extract_text(self) -> str:
        """
        Extracts all human-readable text from the slide's HTML content.

        Uses BeautifulSoup to parse the HTML and get text, with newlines separating elements.
        The result is cached for subsequent calls.

        Returns:
            str: The extracted plain text.
        """
        if self._extracted_text is None:
            soup = BeautifulSoup(self.content_html, 'html.parser')
            self._extracted_text = soup.get_text(separator='\n', strip=True)
        return self._extracted_text

    def find_potential_questions(self) -> List[str]:
        """
        Attempts to find potential questions within the slide's HTML content.

        Strategies include looking for text ending with a question mark, common
        HTML elements used for questions (like <p>, <h1>-<h6>), and text containing
        German question words. Results are cached.

        Returns:
            List[str]: A list of strings, each potentially a question.
        """
        if self._potential_questions is None:
            self._potential_questions = []
            soup = BeautifulSoup(self.content_html, 'html.parser')

            for text_node in soup.find_all(string=True):
                if '?' in text_node:
                    parts = text_node.split('?')
                    for i in range(len(parts) - 1):
                        question = parts[i] + '?'
                        if len(question.strip()) > 10:
                            self._potential_questions.append(question.strip())

            for elem in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                text = elem.get_text(strip=True)
                if text and 10 < len(text) < 500:
                    if text not in self._potential_questions:
                         self._potential_questions.append(text)


            german_question_words = ['wer', 'was', 'wo', 'wann', 'warum', 'wie', 'welche', 'welcher', 'welches', 'wohin', 'woher']
            for text_node in soup.find_all(string=True):
                text_lower = text_node.lower()
                if any(word in text_lower for word in german_question_words) and 10 < len(text_node) < 500:
                    if text_node.strip() not in self._potential_questions:
                        self._potential_questions.append(text_node.strip())
        return self._potential_questions

    def save_html_to_file(self, filename: Optional[str] = None) -> str:
        """
        Saves the slide's HTML content to a local file.

        If no filename is provided, a default filename is generated using the slide's ID.

        Args:
            filename (Optional[str]): The desired filename (or path). If None,
                                      a default is used (e.g., "slide_101.html").

        Returns:
            str: The absolute path to the saved file.
        """
        if not filename:
            filename = f"slide_{self.id}.html"

        filepath = os.path.abspath(filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.content_html)
        logger.info(f"Saved slide HTML to {filepath}")
        return filepath

    def get_slide_analysis(self) -> Dict[str, Any]:
        """
        Provides a comprehensive analysis of the slide's content.

        This includes metadata (ID, title, etc.), counts of forms, details of each form
        (ID, question, fields), potential questions extracted from the text, a snippet
        of the extracted text, and the length of the HTML content.

        Returns:
            Dict[str, Any]: A dictionary containing the slide analysis.
        """
        forms = self.get_forms()
        extracted_full_text = self.extract_text()
        analysis = {
            'slide_id': self.id,
            'title': self.title,
            'kapitel': self.kapitel_id,
            'thema': self.thema_id,
            'forms_count': len(forms),
            'forms': [],
            'potential_questions': self.find_potential_questions(),
            'extracted_text': extracted_full_text[:1000] + "..." if len(extracted_full_text) > 1000 else extracted_full_text,
            'html_length': len(self.content_html)
        }

        for form_obj in forms:
            form_info = {
                'form_id': form_obj.form_id,
                'question': form_obj.question_text,
                'fields_count': len(form_obj.fields),
                'fields': []
            }
            for field in form_obj.fields:
                field_info = {
                    'name': field.name,
                    'type': field.field_type.name,
                    'label': field.label,
                    'required': field.required,
                    'options_count': len(field.options)
                }
                form_info['fields'].append(field_info)
            analysis['forms'].append(form_info)
        return analysis

    def get_forms(self) -> List[FormData]:
        """
        Parses and returns all forms found within the slide's HTML content.

        Uses the FormParser utility. Results are cached.

        Returns:
            List[FormData]: A list of FormData objects representing the forms on the slide.
        """
        if self._forms is None:
            self._forms = []
            try:
                form_tuples = FormParser.extract_forms(self.content_html)
                for form_id, form_html_str in form_tuples:
                    try:
                        form_data = FormParser.parse_form(form_html_str)
                        # Ensure the parsed form_id (if from hash) is consistent or use the one from extract_forms
                        if not form_data.form_id or form_data.form_id.startswith("synthetic-"): # if parse_form generated its own
                             form_data.form_id = form_id # prefer the one from extract_forms if more meaningful
                        self._forms.append(form_data)
                    except FormParsingError as e:
                        logger.warning(f"Failed to parse form '{form_id}' in slide {self.id}: {e}")
                logger.info(f"Found {len(self._forms)} forms in slide {self.id}")
            except Exception as e:
                logger.error(f"Error extracting forms from slide {self.id}: {e}")
        return self._forms

    def get_form_ids(self) -> List[str]:
        """
        Returns a list of all form IDs found in the slide's content.

        Relies on `get_forms()` to parse forms first. Results are cached.

        Returns:
            List[str]: A list of form ID strings.
        """
        if self._form_ids is None:
            self._form_ids = [form.form_id for form in self.get_forms()]
        return self._form_ids

    def get_form_by_id(self, form_id: str) -> Optional[FormData]:
        """
        Retrieves a specific form from the slide by its ID.

        Args:
            form_id (str): The ID of the form to retrieve.

        Returns:
            Optional[FormData]: The FormData object if found, otherwise None.
        """
        for form_obj in self.get_forms():
            if form_obj.form_id == form_id:
                return form_obj
        return None

    def create_form_handler(self, user_id: int, form_id: Optional[str] = None) -> 'Form':
        """
        Creates a Form handler for submitting responses to a form on this slide.

        If `form_id` is not provided, it defaults to the ID of the first form found on the slide.

        Args:
            user_id (int): The ID of the user who will be submitting the form.
            form_id (Optional[str]): The specific ID of the form. If None, the first
                                     form on the slide is used.

        Returns:
            Form: A Form object ready for interaction.

        Raises:
            FormParsingError: If no forms are found on the slide and `form_id` is None.
            NotFoundError: If the theme associated with this slide cannot be found.
        """
        if form_id is None:
            form_ids = self.get_form_ids()
            if not form_ids:
                raise FormParsingError(f"No forms found in slide {self.id}")
            form_id = form_ids[0]

        theme_obj = self._client.get_theme_by_kapitel_thema(self.kapitel_id, self.thema_id)
        if not theme_obj:
            raise NotFoundError(f"Theme not found for kapitel {self.kapitel_id}, thema {self.thema_id}")

        return theme_obj.create_form(
            user_id=user_id,
            form_id=form_id,
            slide_id=self.id
        )

class SlideOrder:
    """
    Represents the order of a specific slide within a theme's sequence.

    Attributes:
        id (int): The unique identifier for this slide order entry.
        kapitel_id (int): The ID of the chapter.
        thema_id (int): The ID of the theme.
        slide_id (int): The ID of the slide being ordered.
        order (int): The numerical order of the slide within the theme.
        additional_attributes (Dict[str, Any]): Any other attributes from the API.
        _client (DDDGermanPlatform): An instance of the API client.
    """
    def __init__(self, platform_client: 'DDDGermanPlatform', id: int, kapitel: int, thema: int, slideId: int, order: int, **kwargs):
        """
        Initializes a SlideOrder object.

        Args:
            platform_client (DDDGermanPlatform): The API client instance.
            id (int): The ID of the slide order record.
            kapitel (int): The chapter ID.
            thema (int): The theme ID.
            slideId (int): The slide ID.
            order (int): The order index.
            **kwargs: Additional attributes from the API response.
        """
        self._client = platform_client
        self.id = id
        self.kapitel_id = kapitel
        self.thema_id = thema
        self.slide_id = slideId
        self.order = order
        self.additional_attributes = kwargs

    def __repr__(self) -> str:
        """
        Provides a string representation of the SlideOrder object.

        Returns:
            str: A string like "<SlideOrder kapitel=1 thema=1 slide_id=101 order=0>".
        """
        return f"<SlideOrder kapitel={self.kapitel_id} thema={self.thema_id} slide_id={self.slide_id} order={self.order}>"

class VocabularyItem:
    """
    Represents a single vocabulary entry, typically a German word and its English translation.

    Attributes:
        id (int): The unique identifier for the vocabulary item.
        kapitel_id (int): The ID of the chapter this item is associated with.
        thema_id (Optional[int]): The ID of the theme this item is specifically associated with, if any.
        german (str): The German word or phrase.
        english (str): The English translation.
        additional_attributes (Dict[str, Any]): Any other attributes from the API (e.g., audio links, plural forms).
        _client (DDDGermanPlatform): An instance of the API client.
    """
    def __init__(self, platform_client: 'DDDGermanPlatform', id: int, kapitel: int, thema: Optional[int], german: str, english: str, **kwargs):
        """
        Initializes a VocabularyItem object.

        Args:
            platform_client (DDDGermanPlatform): The API client instance.
            id (int): The vocabulary item's ID.
            kapitel (int): The chapter ID.
            thema (Optional[int]): The theme ID, if specific to a theme.
            german (str): The German word/phrase.
            english (str): The English translation.
            **kwargs: Additional attributes from the API response.
        """
        self._client = platform_client
        self.id = id
        self.kapitel_id = kapitel
        self.thema_id = thema
        self.german = german
        self.english = english
        self.additional_attributes = kwargs

    def __repr__(self) -> str:
        """
        Provides a string representation of the VocabularyItem object.

        Returns:
            str: A string like "<VocabularyItem id=1 german='Wort' english='Word'>".
        """
        return f"<VocabularyItem id={self.id} german='{self.german}' english='{self.english}'>"

class UserResponse:
    """
    Represents a user's saved response to an exercise or form on a slide.

    Attributes:
        id (int): The unique ID of the response record.
        user_id (int): The ID of the user who made the response.
        kapitel_id (int): The chapter ID related to the response.
        thema_id (int): The theme ID related to the response.
        form_id (str): The ID of the form that was submitted.
        slide_id (int): The ID of the slide where the form was located.
        created_at (str): Timestamp of when the response was created.
        updated_at (str): Timestamp of when the response was last updated.
        form_data_raw (Optional[str]): The raw JSON string of the submitted form data.
        response_text (Optional[str]): A simplified text representation of the response,
                                       often the value of an 'answer' field or the raw formData if not JSON.
        additional_attributes (Dict[str, Any]): Other data returned by the API for this response.
        _client (DDDGermanPlatform): API client instance.
        _parsed_form_data (Optional[Dict[str, str]]): Cached dictionary of parsed form data.
        _form_data_obj (Optional[FormData]): Cached FormData structure for this response's form.
        _slide (Optional[Slide]): Cached Slide object associated with this response.
    """
    def __init__(self, platform_client: 'DDDGermanPlatform', id: int, userId: int, kapitel: int, thema: int, formId: str, slideId: int, createdAt: str, updatedAt: str, formData: Optional[str] = None, response: Optional[str] = None, **kwargs):
        """
        Initializes a UserResponse object.

        Args:
            platform_client (DDDGermanPlatform): The API client instance.
            id (int): Response ID.
            userId (int): User's ID.
            kapitel (int): Chapter ID.
            thema (int): Theme ID.
            formId (str): Form ID.
            slideId (int): Slide ID.
            createdAt (str): Creation timestamp.
            updatedAt (str): Update timestamp.
            formData (Optional[str]): JSON string of submitted data (newer API).
            response (Optional[str]): Plain text response (older API) or fallback.
            **kwargs: Additional attributes from the API response.
        """
        self._client = platform_client
        self.id = id
        self.user_id = userId
        self.kapitel_id = kapitel
        self.thema_id = thema
        self.form_id = formId
        self.slide_id = slideId
        self.created_at = createdAt
        self.updated_at = updatedAt
        self._parsed_form_data: Optional[Dict[str, str]] = None
        self._form_data_obj: Optional[FormData] = None
        self._slide: Optional[Slide] = None

        self.form_data_raw = formData
        self.response_text = response # Prioritize explicit response if available

        if formData and not self.response_text: # If response_text wasn't directly given, try to derive from formData
            try:
                parsed_data = json.loads(formData)
                self._parsed_form_data = parsed_data
                if isinstance(parsed_data, dict):
                    # Common key for single answers, or stringify the dict
                    self.response_text = parsed_data.get('answer', str(parsed_data))
                else: # If formData is a list or other JSON type
                    self.response_text = str(parsed_data)
            except json.JSONDecodeError:
                self.response_text = formData # Use raw string if JSON parsing fails
                logger.warning(f"Failed to parse form data JSON for response {self.id}: {formData[:100]}")
        elif not formData and response: # Only response text provided
             self.response_text = response


        self.additional_attributes = kwargs

    def __repr__(self) -> str:
        """
        Provides a string representation of the UserResponse object.

        Returns:
            str: A string representation including response ID, user ID, form ID, and a preview of the response.
        """
        response_preview = (self.response_text[:30] + "..." if self.response_text and len(self.response_text) > 30 else self.response_text) if self.response_text else "N/A"
        return f"<UserResponse id={self.id} user_id={self.user_id} form_id='{self.form_id}' slide_id={self.slide_id} response='{response_preview}'>"

    def get_form_data(self) -> Dict[str, str]:
        """
        Parses and returns the submitted form data as a dictionary.

        If `form_data_raw` (the JSON string from the API) hasn't been parsed yet,
        this method will parse it.

        Returns:
            Dict[str, str]: The parsed form data. Returns an empty dictionary if
                            `form_data_raw` is missing or cannot be parsed as JSON.
        """
        if self._parsed_form_data is None:
            if self.form_data_raw:
                try:
                    self._parsed_form_data = json.loads(self.form_data_raw)
                    if not isinstance(self._parsed_form_data, dict):
                        # If it's not a dict (e.g. a list or simple string from JSON), wrap it or handle appropriately
                        logger.warning(f"Parsed form data for response {self.id} is not a dictionary: {type(self._parsed_form_data)}")
                        self._parsed_form_data = {'_raw_data': self._parsed_form_data} if self._parsed_form_data is not None else {}

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse form data JSON for response {self.id}: {self.form_data_raw[:100]}")
                    self._parsed_form_data = {} # Default to empty dict on error
            else:
                self._parsed_form_data = {}
        return self._parsed_form_data


    def get_slide(self) -> Optional[Slide]:
        """
        Retrieves the Slide object associated with this user response.

        Fetches theme and slide data via the API client if not already cached.

        Returns:
            Optional[Slide]: The Slide object, or None if it cannot be found.
        """
        if self._slide is None:
            try:
                theme_obj = self._client.get_theme_by_kapitel_thema(self.kapitel_id, self.thema_id)
                if theme_obj:
                    slides = theme_obj.get_slides()
                    for s in slides:
                        if s.id == self.slide_id:
                            self._slide = s
                            break
            except Exception as e:
                logger.error(f"Error getting slide for response {self.id}: {e}")
        return self._slide

    def get_form_structure(self) -> Optional[FormData]:
        """
        Retrieves the FormData structure of the form to which this response was submitted.

        This involves fetching the associated slide and parsing its forms.

        Returns:
            Optional[FormData]: The FormData object for the form, or None if not found.
        """
        if self._form_data_obj is None:
            slide_obj = self.get_slide()
            if slide_obj:
                self._form_data_obj = slide_obj.get_form_by_id(self.form_id)
        return self._form_data_obj

    def get_question_text(self) -> Optional[str]:
        """
        Retrieves the question text associated with the form of this response.

        Returns:
            Optional[str]: The question text, or None if not available.
        """
        form_structure = self.get_form_structure()
        if form_structure:
            return form_structure.question_text
        return None

    def get_field_values(self) -> Dict[str, str]:
        """
        Returns a dictionary of field names to their submitted values for this response.
        This is equivalent to `get_form_data()`.

        Returns:
            Dict[str, str]: A dictionary of submitted field names and values.
        """
        return self.get_form_data()

    def get_field_labels(self) -> Dict[str, str]:
        """
        Retrieves a dictionary mapping field names to their human-readable labels
        for the form associated with this response.

        Returns:
            Dict[str, str]: A dictionary where keys are field names and values are their labels.
                            Returns an empty dictionary if the form structure cannot be determined.
        """
        form_structure = self.get_form_structure()
        if not form_structure:
            return {}
        return {field.name: field.label for field in form_structure.fields if field.label}

    def get_formatted_response(self) -> Dict[str, Dict[str, str]]:
        """
        Provides a formatted representation of the response, combining field labels with submitted values.

        Returns:
            Dict[str, Dict[str, str]]: A dictionary where keys are field names. Each value is
                                       another dictionary with 'label' and 'value' keys.
                                       The label defaults to the field name if no explicit label exists.
        """
        result = {}
        submitted_data = self.get_form_data()
        labels = self.get_field_labels()

        for field_name, value in submitted_data.items():
            result[field_name] = {
                'label': labels.get(field_name, field_name),
                'value': value
            }
        return result

    def update_response(self, new_form_data: Dict[str, str]) -> 'UserResponse':
        """
        Updates this user response on the server with new form data.

        Creates a Form handler and submits the new data.

        Args:
            new_form_data (Dict[str, str]): A dictionary of field names to their new values.

        Returns:
            UserResponse: The updated UserResponse object returned by the server.

        Raises:
            NotFoundError: If the associated theme cannot be found.
            FormSubmissionError: If the submission fails.
        """
        theme_obj = self._client.get_theme_by_kapitel_thema(self.kapitel_id, self.thema_id)
        if not theme_obj:
            raise NotFoundError(f"Theme not found for kapitel {self.kapitel_id}, thema {self.thema_id}")

        form_handler = theme_obj.create_form(
            user_id=self.user_id,
            form_id=self.form_id,
            slide_id=self.slide_id
        )
        return form_handler.submit_form_data(new_form_data)

class Form:
    """
    Handles interactions with a specific form on a slide, such as submitting responses
    and retrieving its structure or previous submissions for a user.

    Attributes:
        user_id (int): The ID of the user interacting with the form.
        kapitel_id (int): The chapter ID where the form resides.
        thema_id (int): The theme ID where the form resides.
        form_id (str): The ID of the form itself.
        slide_id (int): The ID of the slide containing the form.
        _client (DDDGermanPlatform): API client instance.
        _form_data (Optional[FormData]): Cached structure of the form.
        _previous_responses (List[UserResponse]): Cached list of previous responses by the user.
        _last_fetch_time (Optional[float]): Timestamp of the last fetch for previous responses.
    """
    def __init__(self, platform_client: 'DDDGermanPlatform', user_id: int, kapitel_id: int, thema_id: int, form_id: str, slide_id: int):
        """
        Initializes a Form handler.

        Args:
            platform_client (DDDGermanPlatform): The API client instance.
            user_id (int): The ID of the user.
            kapitel_id (int): The chapter ID.
            thema_id (int): The theme ID.
            form_id (str): The form's ID.
            slide_id (int): The slide's ID.
        """
        self._client = platform_client
        self.user_id = user_id
        self.kapitel_id = kapitel_id
        self.thema_id = thema_id
        self.form_id = form_id
        self.slide_id = slide_id
        self._form_data: Optional[FormData] = None
        self._previous_responses: List[UserResponse] = []
        self._last_fetch_time: Optional[float] = None

    def __repr__(self) -> str:
        """
        Provides a string representation of the Form object.

        Returns:
            str: A string representation detailing the form's context.
        """
        return f"<Form user_id={self.user_id} kapitel={self.kapitel_id} thema={self.thema_id} form_id='{self.form_id}' slide_id={self.slide_id}>"

    def get_form_data(self) -> Optional[FormData]:
        """
        Retrieves the structure (fields, question text) of this form.

        Fetches the associated slide and parses its forms if not already cached.

        Returns:
            Optional[FormData]: The FormData object for this form, or None if not found.
        """
        if self._form_data is None:
            try:
                slide_obj = self._get_slide()
                if slide_obj:
                    self._form_data = slide_obj.get_form_by_id(self.form_id)
            except Exception as e:
                logger.error(f"Error getting form data for form {self.form_id}: {e}")
        return self._form_data

    def _get_slide(self) -> Optional[Slide]:
        """
        Internal helper to get the Slide object associated with this form.

        Returns:
            Optional[Slide]: The Slide object, or None if not found.
        """
        try:
            theme_obj = self._client.get_theme_by_kapitel_thema(self.kapitel_id, self.thema_id)
            if not theme_obj:
                logger.warning(f"Theme not found for kapitel {self.kapitel_id}, thema {self.thema_id}")
                return None
            slides = theme_obj.get_slides()
            for s in slides:
                if s.id == self.slide_id:
                    return s
            logger.warning(f"Slide {self.slide_id} not found in theme {self.kapitel_id}/{self.thema_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting slide {self.slide_id}: {e}")
            return None

    def get_question_text(self) -> Optional[str]:
        """
        Retrieves the question text associated with this form.

        Returns:
            Optional[str]: The question text, or None if not available.
        """
        form_structure = self.get_form_data()
        if form_structure:
            return form_structure.question_text
        return None

    def get_field_labels(self) -> Dict[str, str]:
        """
        Retrieves a dictionary mapping field names to their human-readable labels for this form.

        Returns:
            Dict[str, str]: Field names to labels. Empty if form structure is unavailable.
        """
        form_structure = self.get_form_data()
        if not form_structure:
            return {}
        return {field.name: field.label for field in form_structure.fields if field.label}

    def get_previous_responses(self, force_refresh: bool = False) -> List[UserResponse]:
        """
        Retrieves previous responses submitted by the current user for this specific form.

        Uses a time-based cache (60 seconds) to avoid redundant API calls unless
        `force_refresh` is True.

        Args:
            force_refresh (bool): If True, bypasses the cache and fetches fresh data.

        Returns:
            List[UserResponse]: A list of previous UserResponse objects for this form and user.
        """
        current_time = time.time()
        cache_ttl = 60

        if force_refresh or not self._previous_responses or \
           not self._last_fetch_time or (current_time - self._last_fetch_time > cache_ttl):
            try:
                theme_obj = self._client.get_theme_by_kapitel_thema(self.kapitel_id, self.thema_id)
                if not theme_obj:
                    logger.warning(f"Theme not found for kapitel {self.kapitel_id}, thema {self.thema_id}")
                    return []
                all_theme_responses = theme_obj.get_user_responses(user_id=self.user_id)
                self._previous_responses = [
                    r for r in all_theme_responses
                    if r.form_id == self.form_id and r.slide_id == self.slide_id
                ]
                self._last_fetch_time = current_time
            except Exception as e:
                logger.error(f"Error getting previous responses for form {self.form_id}: {e}")
        return self._previous_responses

    def get_latest_response(self) -> Optional[UserResponse]:
        """
        Retrieves the most recent response submitted by the current user for this form.

        Sorts previous responses by their update timestamp.

        Returns:
            Optional[UserResponse]: The latest UserResponse object, or None if no responses exist.
        """
        responses = self.get_previous_responses()
        if not responses:
            return None
        sorted_responses = sorted(responses, key=lambda r: r.updated_at, reverse=True)
        return sorted_responses[0]

    def submit_response(self, response_text: str) -> UserResponse:
        """
        Submits a simple text response for this form.

        The `response_text` is typically wrapped into a JSON structure like `{"answer": "response_text"}`
        before being sent as `formData`. Requires authentication.

        Args:
            response_text (str): The text of the response.

        Returns:
            UserResponse: The UserResponse object created or updated by the submission.

        Raises:
            FormSubmissionError: If the submission fails.
        """
        form_data_payload = {"answer": response_text}
        return self.submit_form_data(form_data_payload)

    def submit_form_data(self, form_data_dict: Dict[str, str]) -> UserResponse:
        """
        Submits a dictionary of form data for this form.

        The `form_data_dict` is JSON stringified and sent as the `formData` field in the payload.
        Requires authentication.

        Args:
            form_data_dict (Dict[str, str]): A dictionary mapping field names to their values.

        Returns:
            UserResponse: The UserResponse object from the server.

        Raises:
            FormSubmissionError: If the submission fails or the server returns an unexpected response.
        """
        payload = {
            "userId": self.user_id,
            "kapitel": self.kapitel_id,
            "thema": self.thema_id,
            "formId": self.form_id,
            "formData": json.dumps(form_data_dict),
            "slideId": self.slide_id
        }
        logger.info(f"Submitting response for form {self.form_id} on slide {self.slide_id}")

        try:
            response_data = self._client._make_request("POST", "responses", json_payload=payload, authenticated=True)
            if isinstance(response_data, dict):
                # Ensure all required keys for UserResponse are present, providing defaults if necessary
                # This is important if the API response might be inconsistent
                response_data.setdefault('id', -1) # Default ID if missing
                response_data.setdefault('userId', self.user_id)
                response_data.setdefault('kapitel', self.kapitel_id)
                response_data.setdefault('thema', self.thema_id)
                response_data.setdefault('formId', self.form_id)
                response_data.setdefault('slideId', self.slide_id)
                response_data.setdefault('createdAt', datetime.utcnow().isoformat() + "Z") # Default timestamp
                response_data.setdefault('updatedAt', datetime.utcnow().isoformat() + "Z") # Default timestamp
                if 'formData' not in response_data and 'response' not in response_data:
                     response_data['formData'] = json.dumps(form_data_dict)


                user_response = UserResponse(self._client, **response_data)

                # Update local cache of previous responses
                if self._previous_responses is not None: # Ensure cache is initialized
                    existing_indices = [i for i, r in enumerate(self._previous_responses) if r.id == user_response.id]
                    if existing_indices: # Should be at most one if IDs are unique
                        self._previous_responses[existing_indices[0]] = user_response
                    else:
                        self._previous_responses.append(user_response)
                else: # Initialize cache if it was None
                    self._previous_responses = [user_response]


                return user_response
            else:
                raise FormSubmissionError(f"Failed to submit response, unexpected data format from server: {type(response_data)}")
        except Exception as e:
            logger.error(f"Error during response submission: {str(e)}")
            logger.error(f"Detailed request payload: {json.dumps(payload, indent=2)}")
            raise FormSubmissionError(f"Failed to submit response: {str(e)}")

    def fill_form(self, **kwargs) -> UserResponse:
        """
        Fills the form with provided field values (as keyword arguments) and submits it.

        Example:
            `form.fill_form(name="John Doe", answer="Option A")`

        Args:
            **kwargs: Keyword arguments where keys are field names and values are the
                      values to submit for those fields.

        Returns:
            UserResponse: The UserResponse object from the submission.

        Raises:
            FormParsingError: If the form structure cannot be retrieved.
            FormSubmissionError: If the submission fails.
        """
        form_structure = self.get_form_data()
        if not form_structure:
            raise FormParsingError(f"Could not get form data for form {self.form_id} to prefill.")

        form_data_to_submit = {}
        for field in form_structure.fields:
            if field.name in kwargs:
                form_data_to_submit[field.name] = kwargs[field.name]
            elif field.value is not None: # Keep existing default values if not overridden
                form_data_to_submit[field.name] = field.value


        # Add any kwargs that were not part of the known fields (e.g. dynamic fields)
        for key, value in kwargs.items():
            if key not in form_data_to_submit:
                form_data_to_submit[key] = value


        return self.submit_form_data(form_data_to_submit)

    def validate_form_data(self, form_data_dict: Dict[str, str]) -> List[str]:
        """
        Validates a dictionary of form data against this form's structure.

        Checks for required fields and ensures that values for select, radio,
        and checkbox fields are among the allowed options.

        Args:
            form_data_dict (Dict[str, str]): The data to validate.

        Returns:
            List[str]: A list of error messages. An empty list means validation passed.
        """
        errors = []
        form_structure = self.get_form_data()
        if not form_structure:
            errors.append(f"Could not retrieve form structure for form {self.form_id} to validate.")
            return errors

        for field in form_structure.fields:
            if field.required and (field.name not in form_data_dict or not form_data_dict[field.name]):
                errors.append(f"Field '{field.label or field.name}' is required.")

            if field.name in form_data_dict and field.options:
                submitted_value = form_data_dict[field.name]
                valid_option_values = [option['value'] for option in field.options]

                if field.field_type in [FormFieldType.SELECT, FormFieldType.RADIO]:
                    if submitted_value not in valid_option_values:
                        errors.append(f"Invalid value '{submitted_value}' for field '{field.label or field.name}'. Valid options: {', '.join(valid_option_values)}.")
                elif field.field_type == FormFieldType.CHECKBOX:
                    # Assuming checkbox values might be submitted as a single value or comma-separated string
                    submitted_values_list = [v.strip() for v in submitted_value.split(',')] if isinstance(submitted_value, str) else [submitted_value]
                    for val in submitted_values_list:
                        if val not in valid_option_values:
                            errors.append(f"Invalid value '{val}' for checkbox field '{field.label or field.name}'. Valid options: {', '.join(valid_option_values)}.")
        return errors

class DDDGermanPlatform:
    """
    Main client for interacting with the DDD German Learning Platform API.

    This class provides methods to fetch chapters, themes, slides, vocabulary,
    and user responses. It handles authentication using a JWT token and manages
    API requests.

    Attributes:
        BASE_URL (str): The base URL for the DDD German API.
        jwt_token (Optional[str]): The JWT token used for authenticated requests.
        timeout (int): The timeout in seconds for API requests.
        _session (requests.Session): A requests session object for persistent connections.
        _all_themas_data_cache (Optional[List[Dict[str, Any]]]): Cache for raw theme data.
        _user_id (Optional[Union[int, str]]): The user ID extracted from the JWT token.
    """
    BASE_URL = "https://api.dddgerman.org/api/"

    def __init__(self, jwt_token: Optional[str] = None, timeout: int = 10):
        """
        Initializes the DDDGermanPlatform API client.

        Args:
            jwt_token (Optional[str]): The JWT token for authentication. If provided,
                                       the user ID will be extracted from it.
            timeout (int): The request timeout in seconds. Defaults to 10.
        """
        self.jwt_token = jwt_token
        self.timeout = timeout
        self._session = requests.Session()
        self._all_themas_data_cache: Optional[List[Dict[str, Any]]] = None
        self._user_id: Optional[Union[int, str]] = None

        if jwt_token:
            self._extract_user_id_from_token()

    def _extract_user_id_from_token(self) -> None:
        """
        Extracts the user ID from the JWT token payload.

        It checks common fields like 'sub', 'userId', 'user_id', 'id', or 'email'.
        The extracted ID is stored in `self._user_id`.
        """
        if not self.jwt_token:
            return

        payload = parse_jwt_token(self.jwt_token)
        logger.debug(f"JWT token payload for user ID extraction: {payload}")

        user_id_fields = ['sub', 'userId', 'user_id', 'id', 'email']
        for field in user_id_fields:
            if field in payload:
                try:
                    self._user_id = int(payload[field])
                    logger.info(f"Extracted numeric user ID {self._user_id} from JWT token field '{field}'.")
                    return
                except (ValueError, TypeError):
                    self._user_id = str(payload[field]) # Store as string if not purely numeric
                    logger.info(f"Extracted string user ID '{self._user_id}' from JWT token field '{field}'.")
                    return
        logger.warning("Could not extract a recognizable user ID from the JWT token payload.")

    def get_user_id(self) -> Optional[Union[int, str]]:
        """
        Returns the user ID extracted from the JWT token.

        Note: The DDD German platform's JWT token might not directly contain a numeric user ID
        in a standard field. This method returns what could be parsed. For operations
        requiring a numeric user ID, ensure it's correctly obtained or provided.

        Returns:
            Optional[Union[int, str]]: The extracted user ID (can be int or string), or None.
        """
        return self._user_id

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, json_payload: Optional[Dict] = None, authenticated: bool = False) -> Any:
        """
        Internal helper to make HTTP requests to the API.

        Handles request construction, authentication headers, and error handling.

        Args:
            method (str): HTTP method (e.g., "GET", "POST").
            endpoint (str): API endpoint path (e.g., "kapitels").
            params (Optional[Dict]): URL parameters for GET requests.
            json_payload (Optional[Dict]): JSON body for POST/PUT requests.
            authenticated (bool): If True, includes the Authorization header with JWT token.

        Returns:
            Any: The JSON response from the API, or raw text if JSON decoding fails.
                 Returns None for 204 No Content responses or empty content.

        Raises:
            AuthenticationError: If `authenticated` is True but no JWT token is set.
            APIConnectionError: For connection or timeout issues.
            BadRequestError: For 400 errors.
            ForbiddenError: For 403 errors.
            NotFoundError: For 404 errors.
            ServerError: For 5xx errors.
            DDDGermanAPIError: For other HTTP errors or unexpected issues.
        """
        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "origin": "https://www.dddgerman.org",
            "pragma": "no-cache",
            "referer": "https://www.dddgerman.org/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        }

        if json_payload:
            headers["Content-Type"] = "application/json"
        if authenticated:
            if not self.jwt_token:
                raise AuthenticationError("JWT token is required for this endpoint but not provided.")
            headers["Authorization"] = f"Bearer {self.jwt_token}"

        logger.info(f"Making {method} request to {url}")
        if params: logger.debug(f"Request params: {params}")
        if json_payload: logger.debug(f"Request JSON payload: {json.dumps(json_payload, indent=2)}")

        response_obj = None
        try:
            response_obj = self._session.request(
                method, url, headers=headers, params=params, json=json_payload, timeout=self.timeout
            )
            status_code = response_obj.status_code
            logger.info(f"Response status code: {status_code} from {url}")

            if status_code == 204 or not response_obj.content:
                return None
            
            response_obj.raise_for_status() # Raises HTTPError for 4xx/5xx responses

            # If we reach here, status code is 2xx and not 204
            try:
                result = response_obj.json()
                if isinstance(result, list):
                    logger.debug(f"Received {len(result)} items in list response from {url}")
                else:
                    logger.debug(f"Received dict response from {url}")
                return result
            except json.JSONDecodeError:
                logger.warning(f"Response from {url} is not valid JSON despite 2xx status. Content: {response_obj.text[:200]}...")
                return response_obj.text # Return raw text if JSON parsing fails

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            try:
                error_content = e.response.json()
                message = error_content.get("message", str(e))
                if isinstance(error_content, dict) and "errors" in error_content and isinstance(error_content["errors"], dict): # ASP.NET Core style errors
                    message_parts = [f"{k}: {', '.join(v)}" for k, v in error_content["errors"].items()]
                    message = f"{message} Details: {'; '.join(message_parts)}"

            except json.JSONDecodeError:
                message = e.response.text if e.response.text else str(e)
            
            logger.error(f"API HTTP Error {status_code} for {url}. Message: {message}")
            if status_code == 400: raise BadRequestError(f"Bad Request (400): {message}")
            elif status_code == 401: raise AuthenticationError(f"Unauthorized (401): {message}. Invalid/missing token or insufficient permissions.")
            elif status_code == 403: raise ForbiddenError(f"Forbidden (403): {message}. You don't have permission.")
            elif status_code == 404: raise NotFoundError(f"Not Found (404): Resource at {url} not found.")
            elif status_code >= 500: raise ServerError(f"Server Error ({status_code}): {message}")
            else: raise DDDGermanAPIError(f"HTTP Error ({status_code}): {message}")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection Error: Failed to connect to {url}. Details: {e}")
            raise APIConnectionError(f"Connection Error: {e}")
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout Error: Request to {url} timed out. Details: {e}")
            raise APIConnectionError(f"Timeout Error: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"An unexpected error occurred during request to {url}: {e}")
            raise DDDGermanAPIError(f"Unexpected request error: {e}")
        except json.JSONDecodeError as e: # Should be caught earlier, but as a safeguard
            response_text_snippet = response_obj.text[:200] if response_obj else "No response object"
            logger.error(f"Failed to decode JSON from {url}. Status: {response_obj.status_code if response_obj else 'N/A'}. Details: {e}. Response: {response_text_snippet}")
            raise DDDGermanAPIError(f"JSON Decode Error from {url}. Response: {response_text_snippet}")


    def set_jwt_token(self, jwt_token: str) -> None:
        """
        Updates the JWT token for subsequent authenticated requests.
        Also attempts to re-extract the user ID from the new token.

        Args:
            jwt_token (str): The new JWT token.
        """
        self.jwt_token = jwt_token
        self._extract_user_id_from_token()

    def get_all_chapters(self) -> List[Chapter]:
        """
        Retrieves a list of all available chapters (Kapitels).

        Returns:
            List[Chapter]: A list of Chapter objects.
        """
        chapters_data = self._make_request("GET", "kapitels")
        chapters = []
        if isinstance(chapters_data, list):
            for chapter_data in chapters_data:
                if isinstance(chapter_data, dict) and "kapitel" in chapter_data and "name" in chapter_data:
                    chapters.append(Chapter(
                        platform_client=self,
                        kapitel_id=chapter_data['kapitel'],
                        name=chapter_data['name'],
                        quizlet_embed_code=chapter_data.get('quizletEmbedCode')
                    ))
                elif isinstance(chapter_data, dict) and "roleId" in chapter_data: # Possible other format
                     logger.debug(f"Skipping non-standard chapter data format (possibly role info): {chapter_data}")
                else:
                    logger.warning(f"Unknown chapter data format encountered: {chapter_data}")
        else:
            logger.warning(f"Expected a list for chapters_data from API, got {type(chapters_data)}. Data: {chapters_data}")
        return chapters

    def get_chapter_by_id(self, kapitel_id: int) -> Optional[Chapter]:
        """
        Retrieves a specific chapter by its ID.

        Args:
            kapitel_id (int): The ID of the chapter to retrieve.

        Returns:
            Optional[Chapter]: The Chapter object if found, otherwise None.
        """
        chapters = self.get_all_chapters()
        for chapter in chapters:
            if chapter.id == kapitel_id:
                return chapter
        return None

    def _fetch_all_themas_data(self) -> List[Dict[str, Any]]:
        """
        Internal method to fetch and cache raw data for all themes (Themas).
        This data is used by Chapter objects to populate their themes.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing raw theme data.
        """
        if self._all_themas_data_cache is None:
            data = self._make_request("GET", "themas")
            if isinstance(data, list):
                self._all_themas_data_cache = data
            else:
                logger.warning(f"Expected a list for _fetch_all_themas_data, got {type(data)}. Using empty list. Data: {data}")
                self._all_themas_data_cache = []
        return self._all_themas_data_cache

    def get_all_themes(self) -> List[Theme]:
        """
        Retrieves a list of all themes (Themas) across all chapters.

        Returns:
            List[Theme]: A list of Theme objects.
        """
        themas_data = self._fetch_all_themas_data()
        themes_list = []
        if isinstance(themas_data, list):
            for thema_data in themas_data:
                if isinstance(thema_data, dict) and 'kapitel' in thema_data and 'thema' in thema_data:
                    themes_list.append(Theme(
                        platform_client=self,
                        kapitel_id=thema_data['kapitel'],
                        thema_id=thema_data['thema'],
                        name=thema_data.get('name', 'Unnamed Theme'),
                        render_vocab=thema_data.get('renderVocab', False),
                        quizlet_embed_code=thema_data.get('quizletEmbedCode')
                    ))
                else:
                    logger.warning(f"Thema data item skipped due to missing 'kapitel' or 'thema' key, or not a dict: {thema_data}")
        return themes_list

    def get_theme_by_kapitel_thema(self, kapitel_id: int, thema_id: int) -> Optional[Theme]:
        """
        Retrieves a specific theme by its parent chapter ID and its own theme ID.

        Args:
            kapitel_id (int): The ID of the parent chapter.
            thema_id (int): The ID of the theme.

        Returns:
            Optional[Theme]: The Theme object if found, otherwise None.
        """
        themes = self.get_all_themes() # Ensures cache is populated if needed
        for theme in themes:
            if theme.kapitel_id == kapitel_id and theme.id == thema_id:
                return theme
        return None

    def get_user_progress(self, user_id: int) -> Dict[str, Any]:
        """
        Calculates and returns a user's progress across all chapters, themes, and slides.

        This involves fetching all content and then all user responses for that content
        to determine completion status.

        Args:
            user_id (int): The ID of the user whose progress is to be fetched.

        Returns:
            Dict[str, Any]: A dictionary detailing the user's progress, including total
                            and completed forms, completion percentages at various levels.
        """
        logger.info(f"Calculating progress for user {user_id}")
        progress = {
            'total_chapters': 0, 'total_themes': 0, 'total_slides': 0,
            'total_forms': 0, 'completed_forms': 0, 'completion_percentage': 0.0,
            'chapters': []
        }
        all_chapters = self.get_all_chapters()
        progress['total_chapters'] = len(all_chapters)

        for chapter_obj in all_chapters:
            chapter_prog = {'id': chapter_obj.id, 'name': chapter_obj.name, 'themes': [], 'total_forms': 0, 'completed_forms': 0, 'completion_percentage': 0.0}
            all_themes = chapter_obj.get_themes()
            progress['total_themes'] += len(all_themes)

            for theme_obj in all_themes:
                theme_prog = {'id': theme_obj.id, 'name': theme_obj.name, 'slides': [], 'total_forms': 0, 'completed_forms': 0, 'completion_percentage': 0.0}
                try:
                    all_slides = theme_obj.get_slides()
                    progress['total_slides'] += len(all_slides)
                    user_responses_for_theme = theme_obj.get_user_responses(user_id=user_id)
                    
                    responded_form_slide_pairs = set()
                    for resp in user_responses_for_theme:
                        if resp.form_id and resp.slide_id is not None: # Ensure both are present
                             responded_form_slide_pairs.add((str(resp.form_id), int(resp.slide_id)))


                    for slide_obj in all_slides:
                        slide_prog = {'id': slide_obj.id, 'title': slide_obj.title, 'forms': [], 'total_forms': 0, 'completed_forms': 0}
                        slide_forms = slide_obj.get_forms()
                        slide_prog['total_forms'] = len(slide_forms)
                        theme_prog['total_forms'] += len(slide_forms)
                        chapter_prog['total_forms'] += len(slide_forms)
                        progress['total_forms'] += len(slide_forms)

                        for form_obj in slide_forms:
                            form_info = {'id': form_obj.form_id, 'question': form_obj.question_text, 'completed': False, 'response': None}
                            if (str(form_obj.form_id), int(slide_obj.id)) in responded_form_slide_pairs:
                                form_info['completed'] = True
                                # Find the specific response text (optional, could be slow if many responses)
                                # For now, just mark as completed.
                                slide_prog['completed_forms'] += 1
                                theme_prog['completed_forms'] += 1
                                chapter_prog['completed_forms'] += 1
                                progress['completed_forms'] += 1
                            slide_prog['forms'].append(form_info)
                        theme_prog['slides'].append(slide_prog)
                    
                    if theme_prog['total_forms'] > 0:
                        theme_prog['completion_percentage'] = round((theme_prog['completed_forms'] / theme_prog['total_forms']) * 100, 2)
                except Exception as e:
                    logger.error(f"Error processing theme {theme_obj.kapitel_id}/{theme_obj.id} for progress: {e}")
                chapter_prog['themes'].append(theme_prog)
            
            if chapter_prog['total_forms'] > 0:
                chapter_prog['completion_percentage'] = round((chapter_prog['completed_forms'] / chapter_prog['total_forms']) * 100, 2)
            progress['chapters'].append(chapter_prog)

        if progress['total_forms'] > 0:
            progress['completion_percentage'] = round((progress['completed_forms'] / progress['total_forms']) * 100, 2)
        
        logger.info(f"Progress calculation for user {user_id} complete.")
        return progress

    def export_user_responses(self, user_id: int, output_file: Optional[str] = None) -> str:
        """
        Exports all responses for a given user to a CSV file.

        The CSV includes details like chapter, theme, slide, form ID, question, response,
        and timestamps.

        Args:
            user_id (int): The ID of the user whose responses are to be exported.
            output_file (Optional[str]): The path for the output CSV file. If None,
                                         a default filename is generated (e.g., "user_123_responses_YYYYMMDD_HHMMSS.csv").

        Returns:
            str: The absolute path to the exported CSV file. Returns an empty string if no responses are found.
        """
        logger.info(f"Exporting responses for user {user_id}")
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"user_{user_id}_responses_{timestamp}.csv"
        
        filepath = os.path.abspath(output_file)
        all_responses_data = []
        chapters = self.get_all_chapters()

        for chapter in chapters:
            themes = chapter.get_themes()
            for theme in themes:
                try:
                    user_responses = theme.get_user_responses(user_id=user_id)
                    for resp in user_responses:
                        slide_title = "N/A"
                        question_text = resp.get_question_text() or "N/A"
                        slide_obj = resp.get_slide() # This can be slow if called repeatedly
                        if slide_obj:
                            slide_title = slide_obj.title

                        all_responses_data.append({
                            'user_id': resp.user_id,
                            'chapter_id': chapter.id,
                            'chapter_name': chapter.name,
                            'theme_id': theme.id,
                            'theme_name': theme.name,
                            'slide_id': resp.slide_id,
                            'slide_title': slide_title,
                            'form_id': resp.form_id,
                            'question': question_text,
                            'response_text': resp.response_text,
                            'form_data_raw': resp.form_data_raw,
                            'created_at': resp.created_at,
                            'updated_at': resp.updated_at
                        })
                except Exception as e:
                    logger.error(f"Error processing theme {theme.kapitel_id}/{theme.id} for export: {e}")

        if all_responses_data:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = all_responses_data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_responses_data)
            logger.info(f"Exported {len(all_responses_data)} responses to {filepath}")
            return filepath
        else:
            logger.warning(f"No responses found for user {user_id} to export.")
            # Create empty file with headers? Or return indication of no data.
            # For now, returning empty path if no data.
            return ""


    def find_forms_by_question(self, search_text: str) -> List[Tuple[FormData, Slide, Theme, Chapter]]:
        """
        Searches for forms where the question text contains the given search string (case-insensitive).

        Args:
            search_text (str): The text to search for within form questions.

        Returns:
            List[Tuple[FormData, Slide, Theme, Chapter]]: A list of tuples, where each tuple
                                                          contains the matching FormData object,
                                                          and its parent Slide, Theme, and Chapter objects.
        """
        logger.info(f"Searching for forms with question containing '{search_text}'")
        results = []
        search_text_lower = search_text.lower()
        chapters = self.get_all_chapters()

        for chapter_obj in chapters:
            themes = chapter_obj.get_themes()
            for theme_obj in themes:
                try:
                    slides = theme_obj.get_slides()
                    for slide_obj in slides:
                        forms = slide_obj.get_forms()
                        for form_data_obj in forms:
                            if form_data_obj.question_text and search_text_lower in form_data_obj.question_text.lower():
                                results.append((form_data_obj, slide_obj, theme_obj, chapter_obj))
                except Exception as e:
                    logger.error(f"Error processing theme {theme_obj.kapitel_id}/{theme_obj.id} during form search: {e}")
        logger.info(f"Found {len(results)} forms matching question search for '{search_text}'.")
        return results

    def get_current_user_responses(self, default_user_id: Optional[int] = None) -> Dict[str, List[UserResponse]]:
        """
        Retrieves all responses for the currently authenticated user (from JWT token).

        If the user ID cannot be extracted from the token, a `default_user_id` can be provided.

        Args:
            default_user_id (Optional[int]): A user ID to use if one cannot be
                                             determined from the JWT token.

        Returns:
            Dict[str, List[UserResponse]]: A dictionary where keys are "kapitelId_themaId" strings
                                           (e.g., "1_2") and values are lists of UserResponse objects
                                           for that theme.

        Raises:
            ValueError: If no user ID can be determined (neither from token nor as default).
        """
        current_user_id = self.get_user_id()
        if current_user_id is None:
            if default_user_id is None:
                raise ValueError("No user ID could be extracted from JWT token and no default user ID provided.")
            current_user_id = default_user_id
            logger.info(f"Using default user ID: {current_user_id} for fetching responses.")
        else:
            logger.info(f"Using user ID from JWT token: {current_user_id} for fetching responses.")
        
        # Ensure current_user_id is int for API calls if it was parsed as string (e.g. email)
        # This depends on what the get_user_responses expects. Assuming it needs an int.
        # If the API can handle string IDs, this conversion might not be needed or could be problematic.
        # For now, let's assume the API expects an int for userId.
        try:
            user_id_for_api = int(current_user_id)
        except ValueError:
             raise ValueError(f"User ID '{current_user_id}' cannot be converted to an integer for API calls.")


        responses_by_theme_key: Dict[str, List[UserResponse]] = {}
        chapters = self.get_all_chapters()

        for chapter_obj in chapters:
            themes = chapter_obj.get_themes()
            for theme_obj in themes:
                try:
                    theme_key = f"{theme_obj.kapitel_id}_{theme_obj.id}"
                    theme_responses = theme_obj.get_user_responses(user_id=user_id_for_api)
                    if theme_responses: # Only add if there are responses
                        responses_by_theme_key[theme_key] = theme_responses
                    logger.debug(f"Found {len(theme_responses)} responses for user {user_id_for_api} in theme {theme_key}")
                except Exception as e:
                    logger.error(f"Error getting responses for theme {theme_obj.kapitel_id}/{theme_obj.id} for user {user_id_for_api}: {e}")
        return responses_by_theme_key

    def get_slide_html(self, kapitel_id: int, thema_id: int, slide_id: int) -> Optional[str]:
        """
        Retrieves the raw HTML content of a specific slide.

        Args:
            kapitel_id (int): The ID of the chapter containing the slide.
            thema_id (int): The ID of the theme containing the slide.
            slide_id (int): The ID of the slide.

        Returns:
            Optional[str]: The HTML content string of the slide, or None if not found.
        """
        theme_obj = self.get_theme_by_kapitel_thema(kapitel_id, thema_id)
        if not theme_obj:
            logger.warning(f"Theme {kapitel_id}/{thema_id} not found when trying to get slide HTML.")
            return None
        
        slides = theme_obj.get_slides()
        for slide_obj in slides:
            if slide_obj.id == slide_id:
                return slide_obj.content_html
        
        logger.warning(f"Slide {slide_id} not found in theme {kapitel_id}/{thema_id} when trying to get HTML.")
        return None

    def analyze_slide(self, kapitel_id: int, thema_id: int, slide_id: int) -> Optional[Dict[str, Any]]:
        """
        Performs and returns a detailed analysis of a specific slide.

        Args:
            kapitel_id (int): The ID of the chapter containing the slide.
            thema_id (int): The ID of the theme containing the slide.
            slide_id (int): The ID of the slide to analyze.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing the slide analysis,
                                      or None if the slide cannot be found.
        """
        theme_obj = self.get_theme_by_kapitel_thema(kapitel_id, thema_id)
        if not theme_obj:
            logger.warning(f"Theme {kapitel_id}/{thema_id} not found when trying to analyze slide.")
            return None

        slides = theme_obj.get_slides()
        for slide_obj in slides:
            if slide_obj.id == slide_id:
                return slide_obj.get_slide_analysis()
        
        logger.warning(f"Slide {slide_id} not found in theme {kapitel_id}/{thema_id} for analysis.")
        return None

