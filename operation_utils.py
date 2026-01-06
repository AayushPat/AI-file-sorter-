"""
OPERATION UTILITIES MODULE

Helper functions for managing operation cards and displaying operation details.
"""

import time


def add_action_card(gui_instance, icon, title, subtitle, bg, action_type=None):
    """Add an action card to the operations log.
    
    Args:
        gui_instance: The FileAdvisorGUI instance
        icon: Icon filename
        title: Card title
        subtitle: Card subtitle (usually path)
        bg: Background color
        action_type: Type of action
        
    Returns:
        int: Operation ID
    """
    # Truncate long paths for cleaner display
    if len(subtitle) > 55:
        subtitle = subtitle[:52] + "..."
    
    # Generate operation ID
    gui_instance.operation_counter += 1
    operation_id = gui_instance.operation_counter
    
    # Store operation info
    op_info = {
        "id": operation_id,
        "action": action_type or title,
        "path": subtitle,
        "icon": icon,
        "timestamp": time.time(),
        "files_scanned": 0,
        "files_moved": 0,
        "duration": 0
    }
    gui_instance.operations.append(op_info)
    
    # Make it clickable with anchor
    html = f"""
    <a href="op_{operation_id}" style="text-decoration:none; color:inherit; display:block;">
    <div style="
        background:{bg};
        border-radius:0px;
        margin:3px 0;
        padding:10px 12px;
        border-top: 2px inset {gui_instance.border_dark};
        border-left: 2px inset {gui_instance.border_dark};
        border-bottom: 2px inset {gui_instance.border_light};
        border-right: 2px inset {gui_instance.border_light};
        cursor:pointer;
    " id="op_{operation_id}">
        <div style="display:flex; align-items:center; gap:10px;">
            <img src='icons/{icon}' width='24' height='24' style='flex-shrink:0; vertical-align:middle;'>
            <div style="flex:1; min-width:0;">
                <div style="color:{gui_instance.accent}; font-size:12px; font-weight:bold; font-family:'Courier New', 'Monaco', monospace; margin-bottom:2px;">{title}</div>
                <div style="color:{gui_instance.text}; font-weight:normal; font-size:10px; font-family:'Courier New', 'Monaco', monospace; opacity:0.75; word-break:break-all;">{subtitle}</div>
    </div>
        </div>
    </div>
    </a>
    """
    gui_instance.log_box.append(html)
    
    return operation_id


def show_operation_details(gui_instance, operation_id):
    """Show detailed stats for a specific operation.
    
    Args:
        gui_instance: The FileAdvisorGUI instance
        operation_id: ID of the operation to show
    """
    # Find the operation
    op = None
    for operation in gui_instance.operations:
        if operation["id"] == operation_id:
            op = operation
            break
    
    if not op:
        gui_instance.operation_detail_label.setText("Operation not found")
        gui_instance.operations_stack.setCurrentIndex(1)  # Switch to detail view anyway
        return
    
    gui_instance.selected_operation_id = operation_id
    
    # Calculate duration
    duration = time.time() - op["timestamp"]
    op["duration"] = duration
    
    # Build detail text with better formatting
    details = f"""
<div style="font-family: 'Courier New', 'Monaco', monospace;">
<h3 style="color: {gui_instance.accent}; margin-bottom: 10px;">{op['action'].replace('_', ' ').title()}</h3>
<p><b>Path:</b> {op['path']}</p>
<p><b>Duration:</b> {duration:.1f}s</p>
<p><b>Files Scanned:</b> {op['files_scanned']}</p>
<p><b>Files Moved:</b> {op['files_moved']}</p>
<p><b>Time:</b> {time.strftime('%H:%M:%S', time.localtime(op['timestamp']))}</p>
</div>
    """.strip()
    
    gui_instance.operation_detail_label.setHtml(details)
    # Switch to detail view
    gui_instance.operations_stack.setCurrentIndex(1)


def update_operation_stats(gui_instance, operation_id, files_scanned=0, files_moved=0):
    """Update stats for a specific operation.
    
    Args:
        gui_instance: The FileAdvisorGUI instance
        operation_id: ID of the operation
        files_scanned: Number of files scanned to add
        files_moved: Number of files moved to add
    """
    for op in gui_instance.operations:
        if op["id"] == operation_id:
            op["files_scanned"] += files_scanned
            op["files_moved"] += files_moved
            # Refresh detail view if this operation is selected
            if gui_instance.selected_operation_id == operation_id:
                show_operation_details(gui_instance, operation_id)
            break

