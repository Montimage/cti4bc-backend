import google.generativeai as genai
import json
import time
import os
from django.conf import settings
from decouple import config
from event.models import Event
from typing import List, Dict, Any


class GeminiService:
    """Service to interact with Google Gemini API for report generation"""
    
    def __init__(self):
        # Configure Gemini API with key from environment variables
        # Get API key from .env file only (secure approach)
        api_key = None
        
        # 1. Try Django settings first
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        
        # 2. Try decouple config (reads from .env file)
        if not api_key:
            try:
                api_key = config('GEMINI_API_KEY', default=None)
            except Exception:
                pass
        
        # 3. Try direct environment variable
        if not api_key:
            api_key = os.environ.get('GEMINI_API_KEY')
        
        # Raise error if no API key found - no hardcoded fallback for security
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not found. Please set GEMINI_API_KEY in your .env file. "
                "Example: GEMINI_API_KEY=your_api_key_here"
            )
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def generate_report(self, prompt: str, events: List[Event]) -> Dict[str, Any]:
        """
        Generate a report using Gemini based on prompt and events data
        
        Args:
            prompt: User-provided prompt for report generation
            events: List of Event objects to analyze
            
        Returns:
            Dict containing generated content, tokens used, and generation time
        """
        start_time = time.time()
        
        try:
            # Build context from events
            events_context = self._build_events_context(events)
            
            # Construct full prompt with context
            full_prompt = self._construct_full_prompt(prompt, events_context)
            
            # Generate content with Gemini
            response = self.model.generate_content(full_prompt)
            
            # Calculate generation time
            generation_time = time.time() - start_time
            
            return {
                'content': response.text,
                'tokens_used': self._estimate_tokens(full_prompt + response.text),
                'generation_time': generation_time,
                'success': True,
                'provider': 'gemini',
                'model': 'gemini-1.5-flash'
            }
            
        except Exception as e:
            return {
                'content': f"Error generating report: {str(e)}",
                'tokens_used': 0,
                'generation_time': time.time() - start_time,
                'success': False,
                'error': str(e),
                'provider': 'gemini',
                'model': 'gemini-1.5-flash'
            }
    
    def _build_events_context(self, events: List[Event]) -> str:
        """Build structured context from events data"""
        context_parts = []
        
        for event in events:
            # Base event information
            event_data = {
                'id': event.id,
                'external_id': event.external_id,
                'shared': event.shared,
                'shared_at': event.shared_at.isoformat() if event.shared_at else None,
                'organization': event.organization.name if event.organization else 'Unknown',
                'arrival_time': event.arrival_time.isoformat() if event.arrival_time else None,
            }
            
            # Add the JSON data from the event
            if event.data:
                event_data['event_details'] = event.data
            
            # Add timing information if available
            timing_info = {}
            if event.timeliness:
                timing_info['timeliness'] = str(event.timeliness)
            if event.extension_time:
                timing_info['extension_time'] = str(event.extension_time)
            if event.anon_time:
                timing_info['anon_time'] = str(event.anon_time)
            if event.sharing_speed:
                timing_info['sharing_speed'] = str(event.sharing_speed)
            
            if timing_info:
                event_data['timing_metrics'] = timing_info
            
            # Add reports count if available
            if hasattr(event, 'reports'):
                event_data['previous_reports_count'] = event.reports.count()
            
            context_parts.append(f"Event {event.id}: {json.dumps(event_data, indent=2)}")
        
        return "\n\n".join(context_parts)
    
    def _construct_full_prompt(self, user_prompt: str, events_context: str) -> str:
        """Construct the full prompt with context injection"""
        system_prompt = """You are a cybersecurity analyst expert in CTI (Cyber Threat Intelligence). 
Your task is to analyze security events and generate professional reports based on the provided data.

Please provide your analysis in a clear, structured format using markdown.
Focus on actionable insights and recommendations."""
        
        full_prompt = f"""{system_prompt}

USER REQUEST:
{user_prompt}

EVENTS DATA TO ANALYZE:
{events_context}

Please generate a comprehensive report based on the above information."""
        
        return full_prompt
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough estimation of tokens used (approximation: 1 token ≈ 4 characters)"""
        return len(text) // 4
