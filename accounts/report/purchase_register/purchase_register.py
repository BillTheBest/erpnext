# ERPNext - web based ERP (http://erpnext.com)
# Copyright (C) 2012 Web Notes Technologies Pvt Ltd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals
import webnotes
from webnotes.utils import flt

def execute(filters=None):
	if not filters: filters = {}
	columns, expense_accounts, tax_accounts = get_columns()
	
	invoice_list = get_invoices(filters)
	invoice_expense_map = get_invoice_expense_map(invoice_list)
	invoice_tax_map = get_invoice_tax_map(invoice_list)
	invoice_po_pr_map = get_invoice_po_pr_map(invoice_list)
	account_map = get_account_details(invoice_list)

	data = []
	for inv in invoice_list:
		# invoice details
		purchase_order = ", ".join(invoice_po_pr_map.get(inv.name, {}).get("purchase_order", []))
		purchase_receipt = ", ".join(invoice_po_pr_map.get(inv.name, {}).get("purchase_receipt", []))
		row = [inv.name, inv.posting_date, inv.supplier, inv.credit_to, 
			account_map.get(inv.credit_to), inv.project_name, inv.bill_no, inv.bill_date, 
			inv.remarks, purchase_order, purchase_receipt]
		
		# map expense values
		for expense_acc in expense_accounts:
			row.append(invoice_expense_map.get(inv.name, {}).get(expense_acc))
		
		# net total
		row.append(inv.net_total)
			
		# tax account
		for tax_acc in tax_accounts:
			row.append(invoice_tax_map.get(inv.name, {}).get(tax_acc))

		# total tax, grand total
		row += [inv.total_tax, inv.grand_total]
		data.append(row)
	
	return columns, data
	
	
def get_columns():
	"""return columns based on filters"""
	columns = [
		"Invoice:Link/Purchase Invoice:120", "Posting Date:Date:80", "Supplier:Link/Supplier:120", 
		"Supplier Account:Link/Account:120", "Account Group:LInk/Account:120", 
		"Project:Link/Project:80", "Bill No::120", "Bill Date:Date:80", "Remarks::150", 
		"Purchase Order:Link/Purchase Order:100", "Purchase Receipt:Link/Purchase Receipt:100"
	]
	
	expense_accounts = webnotes.conn.sql_list("""select distinct expense_head 
		from `tabPurchase Invoice Item` where docstatus = 1 and ifnull(expense_head, '') != '' 
		order by expense_head""")
	tax_accounts = 	webnotes.conn.sql_list("""select distinct account_head 
		from `tabPurchase Taxes and Charges` where parenttype = 'Purchase Invoice' 
		and docstatus = 1 and ifnull(account_head, '') != '' order by account_head""")
	
	columns = columns + [(account + ":Currency:120") for account in expense_accounts] + \
		["Net Total:Currency:120"] + [(account + ":Currency:120") for account in tax_accounts] + \
		["Total Tax:Currency:120"] + ["Grand Total:Currency:120"]

	return columns, expense_accounts, tax_accounts

def get_conditions(filters):
	conditions = ""
	
	if filters.get("company"): conditions += " and company=%(company)s"
	if filters.get("account"): conditions += " and account = %(account)s"

	if filters.get("from_date"): conditions += " and posting_date>=%(from_date)s"
	if filters.get("to_date"): conditions += " and posting_date<=%(to_date)s"

	return conditions
	
def get_invoices(filters):
	conditions = get_conditions(filters)
	return webnotes.conn.sql("""select name, posting_date, credit_to, project_name, supplier, 
		bill_no, bill_date, remarks, net_total, total_tax, grand_total 
		from `tabPurchase Invoice` where docstatus = 1 %s 
		order by posting_date desc, name desc""" % conditions, filters, as_dict=1)
	
def get_invoice_expense_map(invoice_list):
	expense_details = webnotes.conn.sql("""select parent, expense_head, sum(amount) as amount
		from `tabPurchase Invoice Item` where parent in (%s) group by parent, expense_head""" % 
		', '.join(['%s']*len(invoice_list)), tuple([inv.name for inv in invoice_list]), as_dict=1)
	
	invoice_expense_map = {}
	for d in expense_details:
		invoice_expense_map.setdefault(d.parent, webnotes._dict()).setdefault(d.expense_head, [])
		invoice_expense_map[d.parent][d.expense_head] = flt(d.amount)
	
	return invoice_expense_map
	
def get_invoice_tax_map(invoice_list):
	tax_details = webnotes.conn.sql("""select parent, account_head, sum(tax_amount) as tax_amount
		from `tabPurchase Taxes and Charges` where parent in (%s) group by parent, account_head""" % 
		', '.join(['%s']*len(invoice_list)), tuple([inv.name for inv in invoice_list]), as_dict=1)
	
	invoice_tax_map = {}
	for d in tax_details:
		invoice_tax_map.setdefault(d.parent, webnotes._dict()).setdefault(d.account_head, [])
		invoice_tax_map[d.parent][d.account_head] = flt(d.tax_amount)
	
	return invoice_tax_map
	
def get_invoice_po_pr_map(invoice_list):
	pi_items = webnotes.conn.sql("""select parent, purchase_order, purchase_receipt
		from `tabPurchase Invoice Item` where parent in (%s) 
		and (ifnull(purchase_order, '') != '' or ifnull(purchase_receipt, '') != '')""" % 
		', '.join(['%s']*len(invoice_list)), tuple([inv.name for inv in invoice_list]), as_dict=1)
	
	invoice_po_pr_map = {}
	for d in pi_items:
		if d.purchase_order:
			invoice_po_pr_map.setdefault(d.parent, webnotes._dict()).setdefault(
				"purchase_order", []).append(d.purchase_order)
		if d.purchase_receipt:
			invoice_po_pr_map.setdefault(d.parent, webnotes._dict()).setdefault(
				"purchase_receipt", []).append(d.purchase_receipt)
				
	return invoice_po_pr_map
	
def get_account_details(invoice_list):
	account_map = {}
	accounts = list(set([inv.credit_to for inv in invoice_list]))
	for acc in webnotes.conn.sql("""select name, parent_account from tabAccount 
		where name in (%s)""" % ", ".join(["%s"]*len(accounts)), tuple(accounts), as_dict=1):
			account_map[acc.name] = acc.parent_account
						
	return account_map	