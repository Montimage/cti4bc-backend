from django.db.models import Count, Q
from django.utils.html import format_html
from django.contrib.admin import AdminSite
from .models import IPReputationRecord


def get_ip_reputation_stats():
    """Get statistics on IP reputation data for the admin index page"""
    total_count = IPReputationRecord.objects.count()
    if total_count == 0:
        return None
        
    malicious_count = IPReputationRecord.objects.filter(is_malicious=True).count()
    clean_count = IPReputationRecord.objects.filter(is_malicious=False).count()
    unknown_count = IPReputationRecord.objects.filter(is_malicious__isnull=True).count()
    
    # Calculate percentages
    malicious_pct = (malicious_count / total_count) * 100 if total_count > 0 else 0
    clean_pct = (clean_count / total_count) * 100 if total_count > 0 else 0
    unknown_pct = (unknown_count / total_count) * 100 if total_count > 0 else 0
    
    # Get recent malicious IPs (last 7 days)
    from datetime import datetime, timedelta
    recent_date = datetime.now() - timedelta(days=7)
    recent_malicious = IPReputationRecord.objects.filter(
        is_malicious=True, 
        last_checked__gte=recent_date
    )[:5]
    
    # Generate HTML for the stats
    html = f"""
    <div style="margin-top: 20px; margin-bottom: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 5px;">
        <h3 style="margin-top: 0;">IP Reputation Statistics</h3>
        <p><b>Total IPs scanned:</b> {total_count}</p>
        
        <div style="display: flex; margin-bottom: 10px;">
            <div style="background-color: #dc3545; height: 20px; width: {malicious_pct}%;"></div>
            <div style="background-color: #28a745; height: 20px; width: {clean_pct}%;"></div>
            <div style="background-color: #6c757d; height: 20px; width: {unknown_pct}%;"></div>
        </div>
        
        <div style="display: flex; justify-content: space-between; max-width: 400px;">
            <div><span style="display: inline-block; width: 10px; height: 10px; background-color: #dc3545;"></span> Malicious: {malicious_count} ({malicious_pct:.1f}%)</div>
            <div><span style="display: inline-block; width: 10px; height: 10px; background-color: #28a745;"></span> Clean: {clean_count} ({clean_pct:.1f}%)</div>
            <div><span style="display: inline-block; width: 10px; height: 10px; background-color: #6c757d;"></span> Unknown: {unknown_count} ({unknown_pct:.1f}%)</div>
        </div>
    """
    
    # Add recent malicious IPs if available
    if recent_malicious:
        html += "<div style='margin-top: 15px;'><h4>Recent Malicious IPs</h4><ul>"
        for record in recent_malicious:
            html += f"<li>{record.ip_address} - Score: {record.threat_score:.1f}/100 (Last checked: {record.last_checked.strftime('%Y-%m-%d')})</li>"
        html += "</ul></div>"
    
    html += "</div>"
    return format_html(html)


# Monkey patch the original AdminSite.index method to include our stats
original_index = AdminSite.index

def custom_index(self, request, extra_context=None):
    stats = get_ip_reputation_stats()
    if extra_context is None:
        extra_context = {}
    if stats:
        extra_context['ip_reputation_stats'] = stats
    return original_index(self, request, extra_context=extra_context)

AdminSite.index = custom_index
