"""
Pinterest Publisher - Posts pins with images and links to boards
"""
import os
import requests
import json

class PinterestPublisher:
    def __init__(self):
        self.access_token = os.getenv('PINTEREST_ACCESS_TOKEN')
        self.app_id = os.getenv('PINTEREST_APP_ID')
        self.base_url = "https://api.pinterest.com/v5"
        
        # Pinterest API approval is only for Thesis Generator
        self.approved_apps = ['thesis generator', 'thesis', 'essay']
        
        if self.access_token and self.app_id:
            print(f"✅ Pinterest API initialized (App ID: {self.app_id})")
            print(f"⚠️  Pinterest approval limited to: {', '.join(self.approved_apps)}")
        else:
            print("⚠️  Pinterest credentials not found. Skipping Pinterest publishing.")
    
    def _is_approved_app(self, app_name):
        """Check if app is approved for Pinterest posting"""
        app_name_lower = app_name.lower()
        return any(approved in app_name_lower for approved in self.approved_apps)
    
    def _get_boards(self):
        """Get list of user's boards"""
        if not self.access_token:
            return None
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/boards",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('items', [])
            else:
                print(f"❌ Failed to get boards: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error fetching boards: {str(e)}")
            return None
    
    def _select_board(self, app_info):
        """Select appropriate board based on app category"""
        boards = self._get_boards()
        if not boards:
            return None
        
        category = app_info.get('category', 'productivity').lower()
        
        # Try to find category-matching board
        for board in boards:
            board_name = board.get('name', '').lower()
            if category in board_name:
                return board.get('id')
        
        # Use first available board if no match
        if boards:
            return boards[0].get('id')
        
        return None
    
    def _create_pin(self, board_id, title, description, link, image_url):
        """Create a pin on Pinterest"""
        if not self.access_token:
            return None
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # Pinterest API v5 format
        pin_data = {
            'board_id': board_id,
            'title': title[:100],  # Max 100 chars
            'description': description[:500],  # Max 500 chars
            'link': link,
            'media_source': {
                'source_type': 'image_url',
                'url': image_url
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/pins",
                headers=headers,
                json=pin_data
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                return data
            else:
                print(f"❌ Pinterest pin creation failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating pin: {str(e)}")
            return None
    
    def publish(self, article, article_url, app_info):
        """
        Publish article to Pinterest
        
        Args:
            article: Article dict with title, description, featured_image
            article_url: Full URL to the article
            app_info: App metadata including name, category, app_store_link
        
        Returns:
            dict: Publication result with success status and pin URL
        """
        if not self.access_token:
            return {
                'success': False,
                'error': 'Pinterest not configured',
                'platform': 'pinterest'
            }
        
        app_name = app_info.get('name', '')
        
        # Check if app is approved for Pinterest
        if not self._is_approved_app(app_name):
            return {
                'success': False,
                'error': f'Pinterest posting only approved for: {", ".join(self.approved_apps)}',
                'platform': 'pinterest',
                'skipped': True
            }
        
        try:
            # Select board
            board_id = self._select_board(app_info)
            if not board_id:
                return {
                    'success': False,
                    'error': 'No Pinterest board found',
                    'platform': 'pinterest'
                }
            
            # Prepare pin content
            title = article.get('title', 'Check out this app!')[:100]
            description = article.get('description', '')[:500]
            
            # Add app store link to description
            app_store_link = app_info.get('app_store_link', article_url)
            if app_store_link and app_store_link not in description:
                description += f"\n\nDownload: {app_store_link}"
            
            # Get featured image
            image_url = article.get('featured_image')
            if not image_url:
                return {
                    'success': False,
                    'error': 'No featured image available',
                    'platform': 'pinterest'
                }
            
            # Create pin
            pin = self._create_pin(board_id, title, description, article_url, image_url)
            
            if pin:
                pin_id = pin.get('id')
                pin_url = f"https://pinterest.com/pin/{pin_id}/"
                
                print(f"✅ Published to Pinterest")
                print(f"   Pin URL: {pin_url}")
                
                return {
                    'success': True,
                    'url': pin_url,
                    'platform': 'pinterest',
                    'pin_id': pin_id,
                    'board_id': board_id
                }
            else:
                return {
                    'success': False,
                    'error': 'Pin creation failed',
                    'platform': 'pinterest'
                }
            
        except Exception as e:
            print(f"❌ Pinterest publishing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'platform': 'pinterest'
            }
    
    def get_account_info(self):
        """Get Pinterest account information"""
        if not self.access_token:
            return None
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/user_account",
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Failed to get account info: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error getting account info: {str(e)}")
            return None
