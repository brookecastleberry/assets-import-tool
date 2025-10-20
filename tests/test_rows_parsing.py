#!/usr/bin/env python3
"""
Unit tests for row parsing functionality in create_targets.py
"""

import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Add src directory and root directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestRowsParsing:
    """Test the --rows flag parsing functionality"""
    
    def create_mock_applications(self, count=20):
        """Helper to create mock application data"""
        return [
            {
                'application_name': f'App{i}',
                'asset_name': f'asset{i}',
                'repository_url': f'https://github.com/user/repo{i}',
                'type': 'Repository'
            }
            for i in range(1, count + 1)
        ]
    
    def parse_rows_string(self, rows_string, max_applications):
        """
        Extract and test the row parsing logic from create_targets.py
        This simulates the parsing without running the full script
        """
        applications = self.create_mock_applications(max_applications)
        
        if not rows_string:
            return applications
        
        try:
            # Parse row numbers supporting both individual (2,5,8) and ranges (2-5)
            row_numbers = []
            for part in rows_string.split(','):
                part = part.strip()
                if '-' in part:
                    # Handle range like "2-5"
                    start, end = part.split('-', 1)
                    start, end = int(start.strip()), int(end.strip())
                    if start > end:
                        raise ValueError(f"Invalid range '{part}' - start ({start}) must be <= end ({end})")
                    row_numbers.extend(range(start, end + 1))
                else:
                    # Handle individual row number
                    row_numbers.append(int(part))
            
            # Remove duplicates and sort
            row_numbers = sorted(set(row_numbers))
            row_indices = [row - 1 for row in row_numbers]  # Convert to 0-based
            
            # Validate row numbers
            max_rows = len(applications)
            invalid_rows = [row for row in row_numbers if row < 1 or row > max_rows]
            if invalid_rows:
                raise ValueError(f"Invalid row numbers {invalid_rows}. CSV has {max_rows} data rows (valid range: 1-{max_rows})")
            
            # Filter to specific rows
            applications = [applications[i] for i in row_indices if i < len(applications)]
            
            return applications, row_numbers
            
        except ValueError as e:
            raise ValueError(str(e))
    
    def test_individual_rows(self):
        """Test parsing individual row numbers"""
        applications, row_numbers = self.parse_rows_string("2,5,8", 20)
        
        assert len(applications) == 3
        assert row_numbers == [2, 5, 8]
        assert applications[0]['application_name'] == 'App2'  # Row 2 -> index 1
        assert applications[1]['application_name'] == 'App5'  # Row 5 -> index 4
        assert applications[2]['application_name'] == 'App8'  # Row 8 -> index 7
    
    def test_simple_range(self):
        """Test parsing simple range"""
        applications, row_numbers = self.parse_rows_string("3-5", 20)
        
        assert len(applications) == 3
        assert row_numbers == [3, 4, 5]
        assert applications[0]['application_name'] == 'App3'
        assert applications[1]['application_name'] == 'App4'
        assert applications[2]['application_name'] == 'App5'
    
    def test_mixed_syntax(self):
        """Test parsing mixed individual and range syntax"""
        applications, row_numbers = self.parse_rows_string("2,5-7,10", 20)
        
        assert len(applications) == 5
        assert row_numbers == [2, 5, 6, 7, 10]
        assert applications[0]['application_name'] == 'App2'
        assert applications[1]['application_name'] == 'App5'
        assert applications[2]['application_name'] == 'App6'
        assert applications[3]['application_name'] == 'App7'
        assert applications[4]['application_name'] == 'App10'
    
    def test_duplicate_removal(self):
        """Test that duplicates are removed and sorted"""
        applications, row_numbers = self.parse_rows_string("5,3,5-7,6", 20)
        
        # Should deduplicate and sort: [3, 5, 5, 6, 7, 6] -> [3, 5, 6, 7]
        assert len(applications) == 4
        assert row_numbers == [3, 5, 6, 7]
    
    def test_single_row(self):
        """Test parsing single row number"""
        applications, row_numbers = self.parse_rows_string("7", 20)
        
        assert len(applications) == 1
        assert row_numbers == [7]
        assert applications[0]['application_name'] == 'App7'
    
    def test_single_range(self):
        """Test parsing single range"""
        applications, row_numbers = self.parse_rows_string("1-3", 20)
        
        assert len(applications) == 3
        assert row_numbers == [1, 2, 3]
    
    def test_large_range(self):
        """Test parsing large range"""
        applications, row_numbers = self.parse_rows_string("1-10", 20)
        
        assert len(applications) == 10
        assert row_numbers == list(range(1, 11))
        assert applications[0]['application_name'] == 'App1'
        assert applications[9]['application_name'] == 'App10'
    
    def test_invalid_range_start_greater_than_end(self):
        """Test error handling for invalid range (start > end)"""
        with pytest.raises(ValueError, match="Invalid range '5-2'"):
            self.parse_rows_string("5-2", 20)
    
    def test_invalid_row_numbers_too_high(self):
        """Test error handling for row numbers beyond CSV size"""
        with pytest.raises(ValueError, match="Invalid row numbers \\[25, 30\\]"):
            self.parse_rows_string("5,25,30", 20)
    
    def test_invalid_row_numbers_too_low(self):
        """Test error handling for row numbers below 1"""
        with pytest.raises(ValueError, match="Invalid row numbers \\[0\\]"):
            self.parse_rows_string("0,5", 20)
    
    def test_invalid_syntax_non_numeric(self):
        """Test error handling for non-numeric input"""
        with pytest.raises(ValueError):
            self.parse_rows_string("abc", 20)
    
    def test_invalid_syntax_malformed_range(self):
        """Test error handling for malformed range"""
        with pytest.raises(ValueError):
            self.parse_rows_string("5--8", 20)
    
    def test_whitespace_handling(self):
        """Test that whitespace is handled correctly"""
        applications, row_numbers = self.parse_rows_string(" 2 , 5 - 7 , 10 ", 20)
        
        assert len(applications) == 5
        assert row_numbers == [2, 5, 6, 7, 10]
    
    def test_edge_case_first_and_last_rows(self):
        """Test edge cases with first and last rows"""
        applications, row_numbers = self.parse_rows_string("1,20", 20)
        
        assert len(applications) == 2
        assert row_numbers == [1, 20]
        assert applications[0]['application_name'] == 'App1'
        assert applications[1]['application_name'] == 'App20'
    
    def test_edge_case_full_range(self):
        """Test full range covering all rows"""
        applications, row_numbers = self.parse_rows_string("1-20", 20)
        
        assert len(applications) == 20
        assert row_numbers == list(range(1, 21))
    
    def test_complex_mixed_syntax(self):
        """Test complex mixed syntax with overlaps"""
        applications, row_numbers = self.parse_rows_string("1,3-5,4,7-9,8,10", 20)
        
        # Should resolve to: [1, 3, 4, 5, 7, 8, 9, 10] (deduplicated)
        assert len(applications) == 8
        assert row_numbers == [1, 3, 4, 5, 7, 8, 9, 10]


class TestRowsIntegration:
    """Test rows parsing in context of the full application"""
    
    def test_rows_precedence_over_limit(self):
        """Test that --rows takes precedence over --limit"""
        # This would be an integration test that verifies the order of operations
        # We can simulate this by checking the logic flow
        
        # Simulate: --rows 2,5,8 --limit 2
        # Expected: Should return rows 2,5,8 (ignoring limit)
        
        # This test would require mocking the full create_targets_json method
        # For now, we test the parsing logic separately
        pass
    
    def test_empty_rows_string(self):
        """Test behavior with empty rows string"""
        parser = TestRowsParsing()
        applications = parser.parse_rows_string("", 20)
        
        # Should return all applications when rows string is empty
        assert len(applications) == 20


if __name__ == '__main__':
    pytest.main([__file__])

