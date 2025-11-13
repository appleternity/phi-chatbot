"""Centralized fake response patterns for FakeChatModel.

This registry provides structured response patterns for deterministic testing.
All fake responses are organized by agent/context type for easy maintenance.

How to add new response patterns:
1. Identify the agent/context (supervisor, rag, emotional_support)
2. Add keywords or response text to the appropriate section
3. Update FakeChatModel to use the new pattern

Example:
    # Add new medication response
    RESPONSE_PATTERNS["medical_responses"]["fluoxetine"] = (
        "Based on the medical information: Fluoxetine (Prozac) is an SSRI..."
    )
"""

# Supervisor Classification Patterns
SUPERVISOR_CLASSIFICATION = {
    "emotional_keywords": [
        "anxious",
        "feeling",
        "depressed",
        "sad",
        "stressed",
        "worried",
        "emotional",
        "upset",
        "down",
        "struggling",
        "need to talk",
        "need someone",
    ],
    "medical_keywords": [
        "medication",
        "drug",
        "medicine",
        "treatment",
        "dose",
        "dosage",
        "side effect",
        "prescription",
        "antidepressant",
        "ssri",
        "what is",
    ],
    "default_agent": "rag_agent",
}

# RAG Classification Patterns
RAG_CLASSIFICATION = {
    "greeting_keywords": [
        "thank",
        "thanks",
        "hello",
        "hi",
        "hey",
        "goodbye",
        "bye",
    ],
    "medical_keywords": [
        "medication",
        "drug",
        "medicine",
        "treatment",
        "dose",
        "dosage",
        "side effect",
        "prescription",
        "antidepressant",
        "ssri",
        "what is",
        "how does",
        "tell me about",
        "aripiprazole",
        "sertraline",
        "lexapro",
    ],
    "default": "retrieve",
}

# Medical Response Patterns
MEDICAL_RESPONSES = {
    "sertraline": (
        "Based on the medical information: Sertraline (Zoloft) is a selective serotonin reuptake inhibitor (SSRI) antidepressant. "
        "It is commonly used to treat depression, anxiety disorders, OCD, PTSD, and panic disorder. "
        "The typical dosage ranges from 50-200mg daily. Common side effects may include nausea, insomnia, and dizziness. "
        "Always consult with a healthcare provider before starting or changing medication."
    ),
    "zoloft": (
        "Based on the medical information: Sertraline (Zoloft) is a selective serotonin reuptake inhibitor (SSRI) antidepressant. "
        "It is commonly used to treat depression, anxiety disorders, OCD, PTSD, and panic disorder. "
        "The typical dosage ranges from 50-200mg daily. Common side effects may include nausea, insomnia, and dizziness. "
        "Always consult with a healthcare provider before starting or changing medication."
    ),
    "bupropion": (
        "Based on the medical information: Bupropion (Wellbutrin) is a norepinephrine-dopamine reuptake inhibitor (NDRI) antidepressant. "
        "It is used to treat depression and seasonal affective disorder, and also helps with smoking cessation. "
        "The typical dosage ranges from 150-300mg daily. Common side effects may include insomnia, dry mouth, and headache."
    ),
    "wellbutrin": (
        "Based on the medical information: Bupropion (Wellbutrin) is a norepinephrine-dopamine reuptake inhibitor (NDRI) antidepressant. "
        "It is used to treat depression and seasonal affective disorder, and also helps with smoking cessation. "
        "The typical dosage ranges from 150-300mg daily. Common side effects may include insomnia, dry mouth, and headache."
    ),
    "aripiprazole": (
        "Based on the medical information: Aripiprazole is an antipsychotic medication used for schizophrenia and bipolar disorder. "
        "For children, special dosing considerations apply. Always consult a pediatric psychiatrist for proper dosing and monitoring."
    ),
    "antidepressant": (
        "Antidepressants are medications used to treat depression and other mood disorders. "
        "Common types include SSRIs (like Sertraline), SNRIs, and NDRIs (like Bupropion). "
        "They work by adjusting neurotransmitter levels in the brain. Always work with a healthcare provider to find the right treatment."
    ),
    "side effect": (
        "Common side effects of antidepressants can include nausea, changes in appetite, sleep disturbances, and dizziness. "
        "Most side effects are temporary and diminish as your body adjusts. If you experience severe or persistent side effects, "
        "contact your healthcare provider."
    ),
    "default": (
        "I can provide information about medications and mental health treatments based on the retrieved medical information. "
        "What specific medication or treatment would you like to know about?"
    ),
}

# Emotional Support Response Patterns
EMOTIONAL_RESPONSES = {
    "anxious": (
        "I understand that you're feeling anxious, and I want you to know that your feelings are completely valid. "
        "Anxiety can be overwhelming, but you're not alone in this. Would you like to talk more about what's been causing you stress?"
    ),
    "anxiety": (
        "I understand that you're feeling anxious, and I want you to know that your feelings are completely valid. "
        "Anxiety can be overwhelming, but you're not alone in this. Would you like to talk more about what's been causing you stress?"
    ),
    "depressed": (
        "I hear that you're feeling down, and I'm really sorry you're going through this. "
        "It's important to acknowledge these feelings. Remember that it's okay to not be okay sometimes. "
        "I'm here to listen and support you."
    ),
    "sad": (
        "I hear that you're feeling down, and I'm really sorry you're going through this. "
        "It's important to acknowledge these feelings. Remember that it's okay to not be okay sometimes. "
        "I'm here to listen and support you."
    ),
    "default": (
        "I understand you're going through a difficult time. It's completely normal to feel this way. "
        "I'm here to listen and support you. What's been on your mind?"
    ),
}

# Default Responses
DEFAULT_RESPONSES = {
    "general": (
        "I'm here to help with medical questions and emotional support. "
        "How can I assist you today?"
    ),
}

# Combined Response Patterns
RESPONSE_PATTERNS = {
    "supervisor_classification": SUPERVISOR_CLASSIFICATION,
    "rag_classification": RAG_CLASSIFICATION,
    "medical_responses": MEDICAL_RESPONSES,
    "emotional_responses": EMOTIONAL_RESPONSES,
    "default_responses": DEFAULT_RESPONSES,
}
