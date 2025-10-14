-- Define the part ID once at the top
DECLARE @PartID NVARCHAR(50) = 'PL 692';

-- =====================================================
-- IPOValidation Check
-- =====================================================
SELECT *
FROM dbo.IPOValidation
WHERE Product = @PartID
ORDER BY Product, Period DESC;

-- =====================================================
-- Part Usage Check
-- =====================================================
SELECT TOP (1000) 
    company_plant_part,
    endOfMonth,
    SUM(ICUsage + IndirectUsage + DirectUsage) AS TotalUsage
FROM dbo.PartUsage
WHERE company_plant_part LIKE '%' + @PartID + '%'
GROUP BY company_plant_part, endOfMonth
ORDER BY endOfMonth DESC;

-- =====================================================
-- Exemption Check
-- =====================================================
SELECT TOP(1000) Number02, CodeDesc, *
FROM sai_dw.Erp.PartPlant P
JOIN sai_dw.Erp.PartPlant_UD u ON p.sysrowid = u.foreignsysrowid
JOIN sai_dw.Ice.UDCodes c ON p.Company = c.Company
    AND u.Number02 = c.CodeID
    AND CodeTypeID = 'IPOMethods'
    AND p.PartNum = @PartID;

-- =====================================================
-- Part Card Check
-- =====================================================

SELECT Company,PartNum,PartDescription,InActive,RunOut,UserChar1
FROM sai_dw.Erp.Part p
WHERE Company = 'SAINC'
AND PartNum = @PartID;